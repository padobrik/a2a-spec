# Interview questions: catching breaks between agents

For developers who run systems where one agent's output is another agent's
input. The goal is to learn how breaks between agents happen and how teams
find them today, not to pitch a tool. Ask for real incidents, not opinions.
About 20 minutes.

## Questions

1. **Tell me about the last time one agent broke another.** What changed (a
   prompt, a model, a field name, a library), who noticed, and how long after
   the change?

2. **How does data travel between your agents?** Free text in a prompt, JSON,
   typed objects (Pydantic, Zod, dataclasses), a shared state object, tool
   calls? Is the format written down anywhere, or does it live in the code?

3. **What runs before a change to one agent is merged?** Unit tests, evals,
   recorded examples, manual runs, nothing? Which of these would catch a
   renamed or missing field in the output?

4. **When an agent's output changes shape, how do you find out which other
   agents read that field?** Search the code, ask the team, wait for an
   error? How long does that take?

5. **Do you have breaks that raise no error?** For example, a consumer falls
   back to a default because a field is missing, and the result is only
   worse, not broken. How did you notice the last one?

6. **What would you need to trust an automatic check between agents?** What
   would make you turn it off (false alarms, slow runs, setup work, calls to
   a model)?

7. **Who owns the boundary between two agents?** One team, two teams, nobody?
   What happens when the producer team wants to change its output?

## Notes for the interviewer

- Write down the framework, the language, the number of agents and how many
  of the links are typed.
- For questions 1 and 5, ask for the date and the time to detect. These give
  the numbers for the cost of the problem.
- Do not show agent-handshake before question 6, so the answers are not
  shaped by it.
