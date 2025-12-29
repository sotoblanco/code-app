export interface Exercise {
    id: string;
    title: string;
    description: string; // Markdown
    initialCode: string;
    testCode: string; // Hidden test code
    expectedOutput?: string;
}

export const EXERCISES: Exercise[] = [
    {
        id: "ternary-1",
        title: "Ternary Expressions",
        description: `
# Ternary Expressions

Ternaries are a great way to reduce a series of statements, like an \`if/else\` block, to a single expression.

**Example:**
\`\`\`python
# Standard if/else
if number % 2 == 0:
    result = number / 2
else:
    result = (number * 3) + 1

# Ternary
result = number / 2 if number % 2 == 0 else (number * 3) + 1
\`\`\`

## Challenge
Write a function \`check_parity(n)\` that returns **"Even"** if a number is even, and **"Odd"** if it's odd.
    `,
        initialCode: `# Write your solution here
def check_parity(n):
    pass`,
        testCode: `
def test_solution():
    assert check_parity(2) == "Even"
    assert check_parity(3) == "Odd"
    assert check_parity(0) == "Even"
    print("All tests passed!")

if __name__ == "__main__":
    try:
        test_solution()
    except AssertionError:
        print("Tests failed!")
    except Exception as e:
        print(f"Error: {e}")
    `,
    }
];
