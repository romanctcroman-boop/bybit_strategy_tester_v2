"""
Docstring Standards for Bybit Strategy Tester.

This module defines the Google-style docstring format used throughout the project.
All new code should follow these standards.

Example Usage:
    # For functions
    def my_function(arg1: str, arg2: int = 10) -> dict:
        '''Short description of function.

        Longer description if needed, explaining what the function does
        and any important details about its behavior.

        Args:
            arg1: Description of arg1.
            arg2: Description of arg2. Defaults to 10.

        Returns:
            dict: Description of return value with structure:
                - key1: Description
                - key2: Description

        Raises:
            ValueError: When arg1 is empty.
            ConnectionError: When database is unavailable.

        Example:
            >>> result = my_function("test", 5)
            >>> print(result)
            {"status": "ok"}
        '''
        pass

    # For classes
    class MyClass:
        '''Short description of class.

        Longer description explaining the purpose of the class,
        when to use it, and any important behavior notes.

        Attributes:
            attr1 (str): Description of attr1.
            attr2 (int): Description of attr2.

        Example:
            >>> obj = MyClass("value")
            >>> obj.process()
        '''
        pass

    # For modules (at top of file)
    '''
    Module Name

    Short description of what this module provides.

    This module contains:
        - Feature 1: Description
        - Feature 2: Description

    Usage:
        from module import function
        result = function(args)

    Note:
        Any important notes about the module.
    '''
"""

# Docstring template strings for code generators

FUNCTION_DOCSTRING_TEMPLATE = '''
"""
{short_description}

{long_description}

Args:
{args_section}

Returns:
    {return_type}: {return_description}

Raises:
{raises_section}
"""
'''.strip()

CLASS_DOCSTRING_TEMPLATE = '''
"""
{short_description}

{long_description}

Attributes:
{attributes_section}

Example:
    {example}
"""
'''.strip()

MODULE_DOCSTRING_TEMPLATE = '''
"""
{module_name}

{short_description}

This module provides:
{features_list}

Usage:
    {usage_example}
"""
'''.strip()


def check_docstring_quality(docstring: str) -> dict:
    """
    Check the quality of a docstring.

    Args:
        docstring: The docstring to check.

    Returns:
        dict: Quality report with issues found:
            - has_description: Whether it has a description
            - has_args: Whether Args section exists
            - has_returns: Whether Returns section exists
            - issues: List of issues found
    """
    if not docstring:
        return {
            "has_description": False,
            "has_args": False,
            "has_returns": False,
            "issues": ["Missing docstring"],
        }

    issues = []
    lines = docstring.strip().split("\n")

    # Check for description
    has_description = len(lines) > 0 and len(lines[0].strip()) > 10
    if not has_description:
        issues.append("Description too short or missing")

    # Check for Args section
    has_args = "Args:" in docstring

    # Check for Returns section
    has_returns = "Returns:" in docstring or "Return:" in docstring

    # Check for common issues
    if '"""' in docstring[3:-3]:
        issues.append("Possible unclosed docstring quotes")

    if "TODO" in docstring or "FIXME" in docstring:
        issues.append("Contains TODO/FIXME - needs completion")

    if "pass" in docstring.lower() and len(docstring) < 50:
        issues.append("Placeholder docstring")

    return {
        "has_description": has_description,
        "has_args": has_args,
        "has_returns": has_returns,
        "issues": issues,
        "quality_score": sum([has_description, has_args, has_returns]) / 3,
    }


__all__ = [
    "FUNCTION_DOCSTRING_TEMPLATE",
    "CLASS_DOCSTRING_TEMPLATE",
    "MODULE_DOCSTRING_TEMPLATE",
    "check_docstring_quality",
]
