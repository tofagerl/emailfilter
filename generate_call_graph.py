#!/usr/bin/env python3
"""
Generate a call graph for the emailfilter application using pyreverse.
"""

import os
import subprocess

def generate_call_graph():
    """Generate a call graph for the emailfilter application."""
    # Create the graphs directory if it doesn't exist
    os.makedirs("graphs", exist_ok=True)
    
    # Generate the class and package diagrams using pyreverse
    cmd = [
        "pyreverse",
        "-o", "png",  # Output format
        "-p", "emailfilter",  # Project name
        "-d", "graphs",  # Output directory
        "src/emailfilter"  # Target module
    ]
    
    print(f"Running command: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)
    
    # Rename the output files to more descriptive names
    os.rename("graphs/classes_emailfilter.png", "graphs/emailfilter_classes.png")
    os.rename("graphs/packages_emailfilter.png", "graphs/emailfilter_packages.png")
    
    # Generate SVG versions for better viewing
    cmd = [
        "pyreverse",
        "-o", "svg",  # Output format
        "-p", "emailfilter",  # Project name
        "-d", "graphs",  # Output directory
        "src/emailfilter"  # Target module
    ]
    
    print(f"Running command: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)
    
    # Rename the SVG files
    os.rename("graphs/classes_emailfilter.svg", "graphs/emailfilter_classes.svg")
    os.rename("graphs/packages_emailfilter.svg", "graphs/emailfilter_packages.svg")
    
    print("Call graphs generated successfully:")
    print("- Class diagram: graphs/emailfilter_classes.png and graphs/emailfilter_classes.svg")
    print("- Package diagram: graphs/emailfilter_packages.png and graphs/emailfilter_packages.svg")

if __name__ == "__main__":
    generate_call_graph() 