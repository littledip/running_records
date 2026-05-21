#!/usr/bin/env python3
"""Compute factorial of a number."""

def factorial(n):
    """Calculate the factorial of n.
    
    Args:
        n: A non-negative integer
        
    Returns:
        The factorial of n as an integer
        
    Raises:
        ValueError: If n is negative or not an integer
    """
    if not isinstance(n, int):
        raise TypeError(f"Input must be an integer, got {type(n).__name__}")
    if n < 0:
        raise ValueError("Factorial is only defined for non-negative integers")
    
    result = 1
    for i in range(2, n + 1):
        result *= i
    return result

def factorial_iterative(n):
    """Calculate factorial using iterative approach."""
    if not isinstance(n, int) or n < 0:
        raise ValueError("Input must be a non-negative integer")
    
    result = 1
    for i in range(2, n + 1):
        result *= i
    return result

def factorial_recursive(n):
    """Calculate factorial using recursive approach."""
    if not isinstance(n, int) or n < 0:
        raise ValueError("Input must be a non-negative integer")
    
    if n == 0 or n == 1:
        return 1
    return n * factorial_recursive(n - 1)

def main():
    """Main function to demonstrate factorial calculation."""
    print("Factorial Calculator")
    print("=" * 40)
    
    try:
        n = int(input("Enter a non-negative integer: "))
        
        if n < 0:
            print("Error: Factorial is only defined for non-negative integers!")
            return
        
        print(f"\n{n}! = {factorial(n)}")
        print(f"Using iterative method: {factorial_iterative(n)}")
        print(f"Using recursive method: {factorial_recursive(n)}")
        
    except ValueError as e:
        print(f"Error: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")

if __name__ == "__main__":
    main()
