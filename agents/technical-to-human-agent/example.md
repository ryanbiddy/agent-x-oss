## Input

Technical update: We reduced median retrieval latency by 43% by moving our ranking stage from a synchronous CPU-bound service into a batched GPU inference path with pre-computed embeddings and a smaller candidate set.

Audience context: general followers
What to preserve: the 43% figure, the fact that it changes user experience

## Output

The human version:
Search inside our product now feels meaningfully faster.

We cut median retrieval latency by 43% by redesigning how results are ranked behind the scenes. Same product experience, less waiting.

Why it matters:
Users don't care which part of the stack changed. They care that the product responds faster and feels smoother when they're in the middle of real work. This kind of speed improvement compounds across every session.

The analogy:
Think of it like moving from inspecting every package one by one at checkout to pre-sorting them and opening the fast lane - except the system is doing that ranking work in parallel before you ever notice the delay.

Investor/board version:
We improved a core product performance metric by 43%, which directly strengthens user experience and gives us more room to scale usage without degrading responsiveness.
