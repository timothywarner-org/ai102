# Ask for citations to reduce fabrication

**Category:** grounding  
**Source:** prompt-engineering-techniques.pdf

If you instruct the model to cite the source material when it makes statements, those statements are much more likely to be grounded. Asking for citations forces the model to make two errors for every fabrication: the fabricated response and a bad citation. The closer the citation sits to the text it supports, the better; inline citations are stronger mitigations for false content than citations placed at the end.
