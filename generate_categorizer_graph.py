#!/usr/bin/env python3
"""
Generate a detailed call graph for the categorizer.py file.
"""

import ast
import os
import subprocess
from pathlib import Path

class FunctionCallVisitor(ast.NodeVisitor):
    """AST visitor that finds function calls and their targets."""
    
    def __init__(self):
        self.calls = []
        self.current_function = None
        self.functions = set()
        self.function_docstrings = {}
        self.function_args = {}
        
    def visit_FunctionDef(self, node):
        """Visit a function definition."""
        prev_function = self.current_function
        self.current_function = node.name
        self.functions.add(node.name)
        
        # Extract docstring if available
        if (len(node.body) > 0 and 
            isinstance(node.body[0], ast.Expr) and 
            isinstance(node.body[0].value, ast.Str)):
            docstring = node.body[0].value.s.strip().split('\n')[0]  # First line only
            self.function_docstrings[node.name] = docstring
        
        # Extract argument names
        arg_names = [arg.arg for arg in node.args.args]
        self.function_args[node.name] = arg_names
        
        self.generic_visit(node)
        self.current_function = prev_function
        
    def visit_Call(self, node):
        """Visit a function call."""
        if self.current_function:
            # Get the name of the called function
            if isinstance(node.func, ast.Name):
                # Direct function call like foo()
                called_func = node.func.id
                self.calls.append((self.current_function, called_func))
            elif isinstance(node.func, ast.Attribute):
                # Method call like obj.foo()
                called_func = node.func.attr
                self.calls.append((self.current_function, called_func))
        
        self.generic_visit(node)

def categorize_functions(functions):
    """Categorize functions based on their names."""
    categories = {
        "API": [],
        "Initialization": [],
        "Prompt": [],
        "Response": [],
        "Utility": [],
        "Logging": []
    }
    
    for func in functions:
        if func.startswith("initialize") or "init" in func.lower():
            categories["Initialization"].append(func)
        elif "prompt" in func.lower() or "create" in func.lower():
            categories["Prompt"].append(func)
        elif "parse" in func.lower() or "extract" in func.lower() or "validate" in func.lower():
            categories["Response"].append(func)
        elif "log" in func.lower():
            categories["Logging"].append(func)
        elif "api" in func.lower() or "call" in func.lower():
            categories["API"].append(func)
        else:
            categories["Utility"].append(func)
    
    return categories

def generate_dot_file(calls, functions, docstrings, args, filename):
    """Generate a DOT file from the function calls."""
    # Categorize functions
    categories = categorize_functions(functions)
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write('digraph G {\n')
        f.write('  rankdir=TB;\n')
        f.write('  node [shape=box, style=filled, fillcolor=lightblue, fontname="Arial"];\n')
        f.write('  edge [fontname="Arial", fontsize=10];\n')
        
        # Create subgraphs for each category
        for category, funcs in categories.items():
            if funcs:
                f.write(f'  subgraph cluster_{category.lower()} {{\n')
                f.write(f'    label="{category}";\n')
                f.write('    style=filled;\n')
                f.write('    color=lightgrey;\n')
                f.write('    node [style=filled, fillcolor=lightblue];\n')
                
                # Add functions in this category
                for func in funcs:
                    # Add docstring as tooltip if available
                    tooltip = docstrings.get(func, "").replace('"', '\\"')
                    arg_list = ", ".join(args.get(func, []))
                    label = f"{func}\\n({arg_list})"
                    f.write(f'    "{func}" [label="{label}", tooltip="{tooltip}"];\n')
                
                f.write('  }\n')
        
        # Add edges for function calls
        for caller, callee in calls:
            f.write(f'  "{caller}" -> "{callee}";\n')
        
        f.write('}\n')

def generate_categorizer_call_graph():
    """Generate a call graph for the categorizer.py file."""
    # Create the graphs directory if it doesn't exist
    os.makedirs("graphs", exist_ok=True)
    
    # Parse the categorizer.py file
    categorizer_path = Path("src/emailfilter/categorizer.py")
    with open(categorizer_path, 'r', encoding='utf-8') as f:
        tree = ast.parse(f.read())
    
    # Find function calls
    visitor = FunctionCallVisitor()
    visitor.visit(tree)
    
    # Generate DOT file
    dot_file = "graphs/categorizer_call_graph.dot"
    generate_dot_file(
        visitor.calls, 
        visitor.functions, 
        visitor.function_docstrings, 
        visitor.function_args,
        dot_file
    )
    
    # Generate PNG from DOT file
    png_file = "graphs/categorizer_call_graph.png"
    cmd = ["dot", "-Tpng", dot_file, "-o", png_file]
    
    print(f"Running command: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)
    
    # Generate SVG from DOT file (more scalable for viewing)
    svg_file = "graphs/categorizer_call_graph.svg"
    cmd = ["dot", "-Tsvg", dot_file, "-o", svg_file]
    
    print(f"Running command: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)
    
    print("Categorizer call graph generated successfully:")
    print(f"- DOT file: {dot_file}")
    print(f"- PNG file: {png_file}")
    print(f"- SVG file: {svg_file}")

if __name__ == "__main__":
    generate_categorizer_call_graph() 