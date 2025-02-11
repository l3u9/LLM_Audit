# LLM_Audit
## utils.py
utils.py is a collection of functions for parsing code and handling dictionary storage and JSON storage

## ContractManager.py
ContractManager.py is a class that stores a contract list, manages it as a dictionary, and extracts desired values.

## Tracer.py
Tracer.py is a class that traces all dependent functions related to a specific function in a specific contract.

It includes an option called "depth", which is a parameter that determines how deep the tracing should go when tracking dependent functions.

## LLMAudit.py
LLMAudit.py is a class that connects to the LMStudio local LLM API to perform LLM auditing.
### Prompting technique
1. CoT
2. Self-Consistency

### LLM Node
1. Decision Vulerable Node (Decision Node)
2. Review Vulnerable And Report Node (Reviewer Node)


## gui.py
gui.py is a simple GUI program built with PyQt that enables all these functionalities to operate through a graphical user interface.


