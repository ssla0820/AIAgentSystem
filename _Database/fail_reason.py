fail_reasons = {
    'Fail to find element': {
        "AT Fail": {
            "Incorrect order of test case steps": "Steps are executed in the wrong order, causing the test to fail.",
            "Action executed before the previous step is complete": "An action happened too soon, leading to an unexpected state.",
            "Interference from an upper dialog box": "A pop-up or overlay is blocking the target element.",
            "Incorrect locator provided due to locator error": "The locator is incorrect or outdated, preventing element detection."
        },
        "AP Fail": {
            "Locator change": "The locator no longer matches the UI element due to changes in attributes or structure.",
            "No response after an action": "The system did not respond after the action, possibly due to a timeout or stalled process.",
            "UI flow change": "The sequence or logic of the UI has changed, invalidating the test steps."
        },
    },
    'Exception: Image comparison failed.': {
        "AT Fail": {
            "Image comparison similarity threshold set too high or too low": "The threshold is incorrect, causing false positives or false negatives."
        },
        "AP Fail": {
            "Image comparison result is really not as expected": "The captured image differs from the expected one, likely due to UI changes or environment variations."
        },
    },
    'Value is incorrect': {
        "AT Fail": {
            "Incorrect verify value": "The expected value does not match the actual result in the verification step."
        }
    },
    'Exception': {
        "AT Fail": {
            "Incorrect order of test case steps": "Steps are executed in the wrong order, causing the test to fail.",
            "Action executed before the previous step is complete": "An action happened too soon, leading to an unexpected state.",
            "Interference from an upper dialog box": "A pop-up or overlay is blocking the target element."
        },
        "AP Fail": {
            "No response after an action": "The system did not respond after the action, possibly due to a timeout or stalled process.",
            "UI flow change": "The sequence or logic of the UI has changed, invalidating the test steps."
        },
    },
}
