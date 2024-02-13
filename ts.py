import re


def sum_calibration_values_part_two(calibration_document):
    # Mapping of spelled-out numbers to digits
    number_words = {
        'one': '1', 'two': '2', 'three': '3', 'four': '4', 'five': '5',
        'six': '6', 'seven': '7', 'eight': '8', 'nine': '9'
        }

    total_sum = 0
    for line in calibration_document.splitlines():
        # Replace spelled-out numbers with digits
        for word, digit in number_words.items():
            line = re.sub(r'\b{}\b'.format(word), digit, line)

        # Find all digits in the line
        digits = re.findall(r'\d', line)
        if digits:
            # Combine the first and last digit to form a two-digit number
            calibration_value = int(digits[0] + digits[-1])
            total_sum += calibration_value
    return total_sum


# Example usage with a string representing the calibration document
calibration_document = """two1nine
eightwothree
abcone2threexyz
xtwone3four
4nineeightseven2
zoneight234
7pqrstsixteen"""

print(sum_calibration_values_part_two(calibration_document))