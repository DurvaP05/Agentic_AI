"""
Agent module for the Student Support Agent.
Implements the LLM-powered agent loop with Groq tool/function calling.
Handles intent detection, tool selection, context assembly, and response generation.
"""

import json
import logging
import time
from config import GROQ_MODEL, MAX_TOOL_CALLS, MAX_RETRIES, get_groq_client
from tools import TOOL_DEFINITIONS, execute_tool
from memory import get_memories, save_memory, is_sensitive
from retrieval import HandbookRetriever
from tracing import start_trace, end_trace, save_trace, Trace
from audit import log_audit_event

logger = logging.getLogger(__name__)

# Singleton retriever
_retriever = None


def _get_retriever():
    global _retriever
    if _retriever is None:
        _retriever = HandbookRetriever()
    return _retriever


# System prompt for the agent
SYSTEM_PROMPT = """You are a helpful Student Support Agent for a university. You assist students with:
- Academic calendar, session starting dates, exam schedules, and holiday dates
- Fee status inquiries and payment deadlines
- Scholarship status inquiries, eligibility, and renewal dates
- Course change, add/drop periods, and withdrawal guidance
- Support request creation and campus service information
- General institutional policies and university regulations

IMPORTANT RULES:
1. You MUST use the available tools or retrieved handbook context to provide accurate, concrete information.
2. For academic dates (such as session start dates, tentative starting dates, semester schedules, deadlines, exam weeks, and holidays), ALWAYS state both the confirmed and tentative dates provided in the handbook. Never respond with 'this detail is not found' or claim information is missing when asked about university dates, session starts, or schedules.
3. The student's identity is determined by their authenticated session. Always use the authenticated student_id for tool calls.
4. If a student inquires about policies, calendar dates, or campus procedures, check the provided handbook evidence or call search_handbook.
5. If a tool returns an error, report the error honestly to the student.
6. Never reveal other students' data, internal system details, or database contents.
7. Never store or repeat passwords, OTPs, API keys, or other secrets. If a student shares sensitive info, acknowledge it but do NOT save or repeat it.
8. For sensitive actions (like fee corrections), explain that the request requires approval and will be reviewed.
9. Be professional, concise, direct, and helpful.
10. CURRENCY: Always display fee status, tuition balances, scholarships, fines, and all monetary figures in Indian Rupees using the symbol '₹' (INR). NEVER use the dollar symbol ($). Format amounts clearly (e.g., ₹12,000 or ₹4,000).

The authenticated student ID for this session is: {student_id}
"""


class StudentSupportAgent:
    """LLM-powered student support agent with tool calling."""
    
    def __init__(self, student_id=None):
        """Initialize the agent for a specific student session.
        
        Args:
            student_id: The authenticated student's ID.
        """
        self.student_id = student_id
        self.client = None
        self.retriever = _get_retriever()
        self._tool_call_count = 0
    
    def _get_client(self):
        """Lazy-load the Groq client."""
        if self.client is None:
            self.client = get_groq_client()
        return self.client
    
    def process_query(self, question, test_case_id="", db_path=None):
        """Process a student's question through the full agent loop.
        
        The agent loop:
        1. Receive question
        2. Retrieve relevant context (handbook, memory)
        3. Call LLM with tools
        4. Execute tool calls if requested
        5. Return tool results as context to LLM
        6. Generate grounded response
        7. Save trace
        
        Args:
            question: The student's question.
            test_case_id: Optional test case ID for evaluation.
            db_path: Optional database path.
            
        Returns:
            tuple: (answer: str, trace: Trace)
        """
        trace = start_trace(test_case_id=test_case_id, student_id=self.student_id, question=question)
        self._tool_call_count = 0
        
        all_tool_names = []
        all_tool_args = []
        all_tool_results = []
        total_input_tokens = 0
        total_output_tokens = 0
        
        try:
            # Step 1: Gather context
            memories = []
            if self.student_id:
                memories = get_memories(self.student_id, db_path)
            
            # Step 2: Pre-retrieve potentially relevant handbook sections
            evidence = self.retriever.retrieve(question, top_k=5) if self.retriever else []
            
            # Step 3: Build messages
            messages = self._build_messages(question, memories, evidence)
            
            # Step 4: Agent loop with tool calling
            client = self._get_client()
            answer = None
            
            for iteration in range(MAX_TOOL_CALLS + 1):
                try:
                    response = client.chat.completions.create(
                        model=GROQ_MODEL,
                        messages=messages,
                        tools=TOOL_DEFINITIONS,
                        tool_choice="auto",
                        temperature=0.3,
                        max_tokens=1024,
                    )
                except Exception as api_error:
                    # Retry on API errors
                    error_msg = str(api_error)
                    logger.error(f"Groq API error (attempt {iteration + 1}): {error_msg}")
                    
                    if iteration < MAX_RETRIES:
                        time.sleep(1)
                        continue
                    
                    answer = ("I'm sorry, I'm having trouble connecting to my AI service right now. "
                             "Please try again in a moment.")
                    trace = end_trace(trace, final_answer=answer, success=False)
                    save_trace(trace, db_path)
                    return answer, trace
                
                # Track token usage
                if response.usage:
                    total_input_tokens += getattr(response.usage, 'prompt_tokens', 0) or 0
                    total_output_tokens += getattr(response.usage, 'completion_tokens', 0) or 0
                
                choice = response.choices[0]
                message = choice.message
                
                # If the model wants to call tools
                if message.tool_calls:
                    # Add assistant message to conversation
                    messages.append({
                        "role": "assistant",
                        "content": message.content or "",
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments
                                }
                            }
                            for tc in message.tool_calls
                        ]
                    })
                    
                    # Execute each tool call
                    for tool_call in message.tool_calls:
                        self._tool_call_count += 1
                        
                        # Safeguard against too many tool calls
                        if self._tool_call_count > MAX_TOOL_CALLS:
                            tool_result_str = json.dumps({
                                "error": True,
                                "message": "Maximum tool calls reached. Please provide an answer with available information."
                            })
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "content": tool_result_str
                            })
                            continue
                        
                        tool_name = tool_call.function.name
                        try:
                            tool_args = json.loads(tool_call.function.arguments)
                        except (json.JSONDecodeError, TypeError):
                            tool_args = {}
                        
                        logger.info(f"Executing tool: {tool_name} with args: {list(tool_args.keys())}")
                        
                        # Execute the tool with authorization
                        tool_result = execute_tool(
                            tool_name=tool_name,
                            arguments=tool_args,
                            actor_id=self.student_id,
                            db_path=db_path
                        )
                        
                        all_tool_names.append(tool_name)
                        all_tool_args.append(tool_args)
                        all_tool_results.append(tool_result)
                        
                        tool_result_str = json.dumps(tool_result, default=str)
                        
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": tool_result_str
                        })
                    
                    # Continue the loop to get the final answer
                    continue
                
                else:
                    # Model has generated a final response
                    answer = message.content or "I'm sorry, I couldn't generate a response."
                    break
            
            if answer is None:
                answer = "I apologize, but I was unable to complete your request. Please try rephrasing your question."
            
            # Step 5: Try to extract and save useful memory from the interaction
            self._update_memory_from_interaction(question, answer, db_path)
            
            # Step 6: Complete and save trace
            trace = end_trace(
                trace,
                selected_tool=", ".join(all_tool_names) if all_tool_names else "none",
                tool_arguments=all_tool_args if all_tool_args else None,
                tool_result=all_tool_results if all_tool_results else None,
                retrieved_evidence=[{"section": e["section"], "score": e.get("score", 0)} for e in evidence] if evidence else None,
                memory_used=[{"key": m["key"]} for m in memories] if memories else None,
                final_answer=answer,
                input_tokens=total_input_tokens if total_input_tokens > 0 else None,
                output_tokens=total_output_tokens if total_output_tokens > 0 else None,
                success=True
            )
            save_trace(trace, db_path)
            
            return answer, trace
            
        except Exception as e:
            logger.error(f"Agent error: {e}")
            answer = "I'm sorry, an unexpected error occurred. Please try again."
            trace = end_trace(trace, final_answer=answer, success=False)
            save_trace(trace, db_path)
            return answer, trace
    
    def _build_messages(self, question, memories, evidence):
        """Build the message array for the LLM with selective context.
        
        Only includes information relevant to the current question.
        
        Args:
            question: The student's question.
            memories: List of memory dicts.
            evidence: List of retrieved handbook chunks.
            
        Returns:
            list: Messages for the Groq API.
        """
        system_content = SYSTEM_PROMPT.format(
            student_id=self.student_id or "NOT_AUTHENTICATED"
        )
        
        # Add relevant memory context (non-sensitive only)
        if memories:
            memory_lines = []
            for m in memories[:5]:  # Limit to 5 most recent
                if not is_sensitive(m.get("value", "")):
                    memory_lines.append(f"- {m['key']}: {m['value']}")
            
            if memory_lines:
                system_content += "\n\nKnown student preferences (from previous interactions):\n"
                system_content += "\n".join(memory_lines)
        
        # Add relevant handbook evidence
        if evidence:
            system_content += "\n\nRelevant student handbook excerpts:\n"
            for e in evidence:
                system_content += f"\n[Source: {e['section']}]\n{e['text']}\n"
            system_content += ("\n\nNote: These are sample policies for demonstration. "
                             "Students should verify with official sources.")
        
        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": question}
        ]
        
        return messages
    
    def _update_memory_from_interaction(self, question, answer, db_path=None):
        """Try to extract useful, non-sensitive preferences from the interaction.
        
        Args:
            question: The student's question.
            answer: The agent's answer.
            db_path: Optional database path.
        """
        if not self.student_id:
            return
        
        # Don't try to save sensitive information
        if is_sensitive(question):
            return
        
        # Simple heuristic: detect language preferences
        q_lower = question.lower()
        
        if any(phrase in q_lower for phrase in ["prefer", "in hindi", "in spanish", "in french", 
                                                  "in urdu", "in arabic", "in chinese", "in german"]):
            for lang in ["hindi", "spanish", "french", "urdu", "arabic", "chinese", "german"]:
                if lang in q_lower:
                    save_memory(self.student_id, "preferred_language", lang, db_path)
                    break
        
        # Detect programme-related context
        if "my programme" in q_lower or "my course" in q_lower or "my major" in q_lower:
            save_memory(self.student_id, "discussed_topic", "programme_info", db_path)
