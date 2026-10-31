"""
Agent reasoning loop for Assignment 1 - Intelligent Student Support Agent.
Implements the autonomous ReAct decision cycle, tool calling, context selection, and tracing.
"""

import json
import logging
import time
from config import GROQ_MODEL, MAX_TOOL_CALLS, MAX_RETRIES, get_groq_client
from tools import TOOL_DEFINITIONS, execute_tool
from memory import get_memories, save_memory, is_sensitive
from retrieval import HandbookRetriever
from tracing import start_trace, end_trace, save_trace, Trace

logger = logging.getLogger(__name__)

_retriever = None


def _get_retriever():
    global _retriever
    if _retriever is None:
        _retriever = HandbookRetriever()
    return _retriever


SYSTEM_PROMPT = """You are a helpful Intelligent Student Support Agent for a university.
The university currently offers two active degree programs:
1. Big Data Analytics (BDA)
2. AI & Data Science

You assist students with:
- Academic calendar, session starting dates, exam schedules, and holiday dates
- Tuition fee status inquiries and payment deadlines
- Scholarship status inquiries, eligibility, and renewal dates
- Course change, add/drop periods, and withdrawal guidance
- Support request creation and campus service information
- General institutional policies and university regulations

IMPORTANT RULES:
1. You MUST use the available tools or retrieved handbook context to provide accurate, concrete information.
2. For academic dates (such as session start dates, tentative starting dates, semester schedules, deadlines, exam weeks, and holidays), ALWAYS state both the confirmed and tentative dates provided in the handbook. Never claim information is missing when asked about university dates.
3. If a student inquires about policies, calendar dates, or campus procedures, check the provided handbook evidence or call search_handbook.
4. If a tool returns an error, report the error honestly to the student.
5. Never store or repeat passwords, OTPs, API keys, or other secrets. If a student shares sensitive info, acknowledge it but do NOT save or repeat it.
6. Be professional, concise, direct, and helpful.
7. CURRENCY: Always display fee status, tuition balances, scholarships, fines, and all monetary figures in Indian Rupees using the symbol '₹' (INR). NEVER use the dollar symbol ($). Format amounts clearly (e.g., ₹12,000 or ₹4,000).

Current student ID for this session: {student_id}
"""


class StudentSupportAgent:
    """LLM-powered student support agent with autonomous tool calling."""

    def __init__(self, student_id=None):
        self.student_id = student_id
        self.client = None
        self.retriever = _get_retriever()
        self._tool_call_count = 0

    def _build_system_prompt(self):
        return SYSTEM_PROMPT.format(student_id=self.student_id or "Not provided")

    def _get_client(self):
        if self.client is None:
            self.client = get_groq_client()
        return self.client

    def process_query(self, question, test_case_id="", db_path=None):
        """Process a student's question through the ReAct agent loop."""
        trace = start_trace(question=question, student_id=self.student_id, test_case_id=test_case_id)
        
        all_tool_names = []
        all_tool_args = []
        all_tool_results = []
        total_input_tokens = 0
        total_output_tokens = 0

        try:
            # 1. Gather context: persistent memories
            memories = []
            if self.student_id:
                memories = get_memories(self.student_id, db_path)

            # 2. Pre-retrieve relevant handbook sections
            evidence = self.retriever.retrieve(question, top_k=5) if self.retriever else []

            # 3. Build selective context messages
            messages = self._build_messages(question, memories, evidence)

            # 4. Agent loop with tool calling
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
                    logger.error(f"Groq API error (iteration {iteration + 1}): {api_error}")
                    if iteration < MAX_RETRIES:
                        time.sleep(1)
                        continue
                    answer = "I'm sorry, I'm having trouble connecting to my AI service right now. Please try again in a moment."
                    trace = end_trace(trace, final_answer=answer, success=False)
                    save_trace(trace, db_path)
                    return answer, trace

                if response.usage:
                    total_input_tokens += getattr(response.usage, 'prompt_tokens', 0) or 0
                    total_output_tokens += getattr(response.usage, 'completion_tokens', 0) or 0

                choice = response.choices[0]
                message = choice.message

                if message.tool_calls:
                    messages.append({
                        "role": "assistant",
                        "content": message.content or "",
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments,
                                }
                            }
                            for tc in message.tool_calls
                        ]
                    })

                    for tool_call in message.tool_calls:
                        func_name = tool_call.function.name
                        try:
                            func_args = json.loads(tool_call.function.arguments)
                        except json.JSONDecodeError:
                            func_args = {}

                        all_tool_names.append(func_name)
                        all_tool_args.append(func_args)

                        # Provide student_id if not present
                        if "student_id" in func_args and not func_args["student_id"] and self.student_id:
                            func_args["student_id"] = self.student_id
                        elif "student_id" not in func_args and self.student_id and func_name in ["check_fee_status", "check_scholarship_status"]:
                            func_args["student_id"] = self.student_id

                        tool_result = execute_tool(func_name, func_args, db_path=db_path)
                        all_tool_results.append(tool_result)

                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": json.dumps(tool_result)
                        })
                else:
                    answer = message.content or "I have processed your request."
                    break

            if answer is None:
                answer = "I was unable to complete your request. Please contact student services for assistance."

            # Update memory if user provided general non-sensitive preferences
            if self.student_id:
                self._update_memory_from_interaction(question, answer, db_path)

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
            logger.error(f"Unexpected agent error: {e}")
            answer = f"An unexpected error occurred: {str(e)}"
            trace = end_trace(trace, final_answer=answer, success=False)
            save_trace(trace, db_path)
            return answer, trace

    def _build_messages(self, question, memories, evidence):
        """Construct the LLM message array with selective context."""
        system_content = SYSTEM_PROMPT.format(student_id=self.student_id or "STU001")

        if memories:
            memory_lines = [f"- {m['key']}: {m['value']}" for m in memories if not is_sensitive(m.get('value', ''))]
            if memory_lines:
                system_content += "\n\nKnown student preferences (from memory):\n" + "\n".join(memory_lines)

        if evidence:
            system_content += "\n\nRelevant student handbook excerpts:\n"
            for e in evidence:
                system_content += f"\n[Source: {e['section']}]\n{e['text']}\n"

        return [
            {"role": "system", "content": system_content},
            {"role": "user", "content": question}
        ]

    def _update_memory_from_interaction(self, question, answer, db_path=None):
        """Extract and persist useful, non-sensitive context across sessions."""
        q_lower = question.lower()
        if "i prefer" in q_lower or "call me" in q_lower:
            parts = question.split("prefer")
            if len(parts) > 1 and not is_sensitive(parts[1]):
                save_memory(self.student_id, "preference", parts[1].strip()[:100], db_path)

