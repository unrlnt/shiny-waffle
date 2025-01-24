from ortools.sat.python import cp_model
import datetime
from import_db import create_connection

def datetime_to_int(dt):
    return int(dt.timestamp())

def int_to_datetime(ts):
    return datetime.datetime.fromtimestamp(ts)

class Task:
    def __init__(self, name, start_date, deadline, duration, priority, category):
        self.name = name
        self.start_date = datetime_to_int(start_date)
        self.deadline = datetime_to_int(deadline)
        self.duration = duration  # In minutes
        self.priority = priority  # 0 to 1
        self.category = category

def create_time_slots(schedules, start_date, end_date):
    slots = []
    current_date = start_date
    while current_date <= end_date:
        weekday = current_date.strftime("%A")
        for category, schedule_list in schedules.items():
            for schedule in schedule_list:
                if weekday in schedule["days"]:
                    start_hour, end_hour = schedule["hours"]
                    start_time = datetime.datetime.combine(current_date, datetime.time(start_hour))
                    end_time = datetime.datetime.combine(current_date, datetime.time(end_hour))
                    current_slot = start_time
                    while current_slot < end_time:
                        next_slot = current_slot + datetime.timedelta(minutes=5)
                        slots.append((datetime_to_int(current_slot), datetime_to_int(next_slot), category))
                        current_slot = next_slot
        current_date += datetime.timedelta(days=1)
    return slots

def combine_consecutive_slots(task_schedule):
    combined_schedule = {}
    for task, slots in task_schedule.items():
        if not slots:
            continue
        day_slots = {}
        for start, end in slots:
            day = int_to_datetime(start).date()
            if day not in day_slots:
                day_slots[day] = []
            day_slots[day].append((start, end))
        combined_schedule[task] = []
        for day, daily_slots in day_slots.items():
            daily_slots.sort()  # Ensure the slots are in order
            combined = [daily_slots[0]]
            for current_start, current_end in daily_slots[1:]:
                last_start, last_end = combined[-1]
                if current_start == last_end:  # Extend the current range
                    combined[-1] = (last_start, current_end)
                else:
                    combined.append((current_start, current_end))
            combined_schedule[task].extend(combined)
    return combined_schedule

# Define tasks
def get_tasks():
    connection = create_connection()
    if connection:
        cursor = connection.cursor(dictionary=True)
        query = "SELECT * FROM tasks WHERE status = 'pending' ORDER BY priority DESC, deadline ASC"
        cursor.execute(query)
        tasks = cursor.fetchall()
        cursor.close()
        connection.close()
        return tasks
    return []

def transform_tasks(db_tasks):
    task_objects = []
    for row in db_tasks:
        name = row['name']
        start_time = datetime.datetime.strptime(row['start_time'], "%Y-%m-%d %H:%M:%S")
        deadline = datetime.datetime.strptime(row['deadline'], "%Y-%m-%d %H:%M:%S")
        duration = row['duration']
        priority = row['priority']
        category = row['category']
        task_objects.append(Task(name, start_time, deadline, duration, priority, category))
    return task_objects

db_tasks = get_tasks()
print("Fetched Tasks:", db_tasks)

tasks = transform_tasks(db_tasks)
print("Parsed Tasks:", tasks)

# Define schedules
def get_schedules():
    connection = create_connection()
    if connection:
        cursor = connection.cursor(dictionary=True)
        query = "SELECT * FROM schedules"
        cursor.execute(query)
        schedules = cursor.fetchall()
        cursor.close()
        connection.close()
        return schedules
    return []

fetched_schedules = get_schedules()
print("Fetched Schedules:", fetched_schedules)

def transform_schedules(db_schedules):
    schedules = {}
    for row in db_schedules:
        category = row['category']
        day = row['day_of_week']
        start_time = row['start_hour']
        end_time = row['end_hour']
        
        if category not in schedules:
            schedules[category] = []
        schedules[category].append({"days": [day], "hours": (start_time, end_time)})
    return schedules

db_schedules = get_schedules()
schedules = transform_schedules(db_schedules)
print("Parsed Schedules:", schedules)

# Generate 5-minute slots for all schedules
start_date = datetime.datetime(2025, 1, 22)
end_date = datetime.datetime(2025, 1, 31)
all_slots = create_time_slots(schedules, start_date, end_date)

# Initialize the model
model = cp_model.CpModel()

# Create variables for tasks
task_starts = {}
task_ends = {}
task_intervals = []
task_vars = []

for task in tasks:
    valid_slots = [(start, end) for start, end, category in all_slots if category == task.category and start >= task.start_date and end <= task.deadline]
    valid_start_times = [start for start, _ in valid_slots]

    if not valid_start_times:
        raise ValueError(f"No valid slots available for task: {task.name}")

    start_var = model.NewIntVar(min(valid_start_times), max(valid_start_times), f"{task.name}_start")
    end_var = model.NewIntVar(min(valid_start_times), max(valid_start_times), f"{task.name}_end")

    model.Add(end_var == start_var + task.duration * 60)

    # Add splitting logic to split tasks into chunks
    remaining_duration = task.duration * 60
    split_intervals = []

    for start, end in valid_slots:
        slot_duration = end - start

        if remaining_duration <= 0:
            break

        overlap_duration = min(remaining_duration, slot_duration)

        split_start = model.NewIntVar(start, end - overlap_duration, f"{task.name}_split_start_{len(split_intervals)}")
        split_end = model.NewIntVar(start + overlap_duration, end, f"{task.name}_split_end_{len(split_intervals)}")
        split_interval = model.NewIntervalVar(split_start, overlap_duration, split_end, f"{task.name}_split_interval_{len(split_intervals)}")

        model.Add(split_start >= start)
        model.Add(split_end <= end)
        model.Add(split_end - split_start == overlap_duration)

        split_intervals.append(split_interval)
        remaining_duration -= overlap_duration

    if remaining_duration > 0:
        raise ValueError(f"Task {task.name} cannot be fully scheduled within its constraints.")

    task_starts[task.name] = start_var
    task_ends[task.name] = end_var
    task_intervals.extend(split_intervals)
    task_vars.append((task, split_intervals))

# Objective: Maximize priority-based scheduling
objective = sum(task.priority * task_starts[task.name] for task, _ in task_vars)
model.Maximize(objective)

# Solve the model
solver = cp_model.CpSolver()
status = solver.Solve(model)

# Output results
if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
    task_schedule = {task.name: [] for task, _ in task_vars}
    for task, intervals in task_vars:
        for interval in intervals:
            start = solver.Value(interval.StartExpr())
            end = solver.Value(interval.EndExpr())
            task_schedule[task.name].append((start, end))

    combined_schedule = combine_consecutive_slots(task_schedule)
    for task, slots in combined_schedule.items():
        print(f"{task}:")
        for start, end in slots:
            print(f"  Start at {int_to_datetime(start)}, End at {int_to_datetime(end)}")
else:
    print("No solution found.")
