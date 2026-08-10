# Temperature and Top_p parameters

**Category:** parameters  
**Source:** prompt-engineering-techniques.pdf

Temperature changes the randomness of the output and can be set between 0 and 2. A higher value like 0.7 makes output more random and divergent; a lower value like 0.2 makes it more focused and concrete. A fictional story suits a higher temperature, a legal document a much lower one. Top_p (top probability) is a similar control that works differently. The general recommendation is to alter only one of these two at a time, not both.
