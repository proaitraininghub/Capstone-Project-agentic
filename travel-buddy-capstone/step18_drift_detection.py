"""
step18_drift_detection.py        (PART 4: Online Evaluation - Drift Detection)
===========================================================================
NEW IDEA: one score on its own means little. Was 3.8 out of 5 good or
bad? What matters is the TREND. Drift detection compares the AVERAGE
score from one week to the next and raises an alarm when it falls.

This file needs NO Azure connection. The weekly scores below are
pretend data, the kind step 17 would collect every day.

Run it:   python step18_drift_detection.py
"""

# Pretend daily average scores (out of 5) for three weeks
DAILY_SCORES = {
    "week 1": [4.2, 4.3, 4.1, 4.4, 4.2, 4.3, 4.1],
    "week 2": [4.0, 4.1, 3.9, 4.0, 3.8, 3.9, 3.7],    # a decline begins
    "week 3": [3.5, 3.4, 3.6, 3.3, 3.2, 3.4, 3.1],    # and continues
}

ALERT_IF_DROP_MORE_THAN = 0.3      # points


def average(numbers):
    return sum(numbers) / len(numbers)


previous_average = None
for week, scores in DAILY_SCORES.items():
    this_average = average(scores)
    line = f"{week}: average {this_average:.2f}"

    if previous_average is not None:
        drop = previous_average - this_average
        line += f"   (change {-drop:+.2f})"
        if drop > ALERT_IF_DROP_MORE_THAN:
            line += "   <-- ALERT: quality is drifting down!"

    print(line)
    previous_average = this_average

print("\nWhen an alert fires, ask: did we deploy a change? did a tool break?")
print("did users start asking new kinds of questions? Check your traces (step 6).")
