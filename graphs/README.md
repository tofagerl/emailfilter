# Function Call Graphs for EmailFilter

This directory contains call graphs generated for the EmailFilter application.

## Available Graphs

### 1. Overall Application Structure

- **`emailfilter_classes.png`/`emailfilter_classes.svg`**: Class diagram showing the relationships between classes in the application.
- **`emailfilter_packages.png`/`emailfilter_packages.svg`**: Package diagram showing the dependencies between modules.

### 2. Categorizer Module Call Graph

- **`categorizer_call_graph.png`/`categorizer_call_graph.svg`**: Detailed call graph for the categorizer module, showing function calls and their relationships.

## Graph Legend

### Categorizer Call Graph

Functions are grouped by their purpose:

- **Initialization**: Functions related to initializing the OpenAI client and other setup tasks
- **API**: Functions that interact with external APIs (like OpenAI)
- **Prompt**: Functions that create prompts for the OpenAI API
- **Response**: Functions that parse and process responses from the API
- **Logging**: Functions related to logging
- **Utility**: Miscellaneous utility functions

Each function box shows:

- Function name
- Parameters in parentheses
- Arrows indicate function calls (A → B means function A calls function B)

## How to View

- PNG files can be viewed in any image viewer
- SVG files provide better quality when zoomed and can be viewed in web browsers or vector graphics editors

## How to Regenerate

To regenerate these graphs, run:

```bash
python generate_call_graph.py       # For overall application structure
python generate_categorizer_graph.py # For categorizer module call graph
```
