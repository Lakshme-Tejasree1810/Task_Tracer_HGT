from fastapi import FastAPI, Request, Form, HTTPException, Depends, Body
from fastapi.templating import Jinja2Templates
from fastapi.responses import FileResponse, RedirectResponse, HTMLResponse, JSONResponse
from pymongo import MongoClient
from fastapi.middleware.cors import CORSMiddleware
import re
from bson import ObjectId
from datetime import datetime
import matplotlib.pyplot as plt
import io
import base64

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

templates = Jinja2Templates(directory="templates")
client = MongoClient('mongodb://localhost:27017/')
db = client['homepage']
users_collection = db['users']
tasks_collection = db['tasks']

@app.get("/")
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/login")
async def login(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/register")
async def get_register(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

def is_valid_email(email):
    pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    return re.match(pattern, email) is not None

def create_user(username, email, password, role):
    user = {
        "_id": str(ObjectId()),
        "username": username,
        "email": email,
        "password": password,
        "role": role
    }
    users_collection.insert_one(user)
    return user["_id"]

def check_login(email, password):
    user = users_collection.find_one({"email": email, "password": password})
    return user

@app.post("/login")
async def login(email: str = Form(...), password: str = Form(...)):
    user = check_login(email, password)
    if user:
        return JSONResponse(content={"message": "Login successful", "role": user["role"], "username": user["username"]})
    else:
        return JSONResponse(content={"message": "Login failed"}, status_code=401)

@app.get("/logout")
async def logout(request: Request):
    return RedirectResponse(url="/")

@app.post("/register")
def post_register(
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    repassword: str = Form(...),
    role: str = Form(...)
):
    if password != repassword:
        return JSONResponse(content={"message": "Passwords do not match"}, status_code=400)
    
    if not is_valid_email(email):
        return JSONResponse(content={"message": "Invalid email format"}, status_code=400)
    
    existing_user = users_collection.find_one({"$or": [{"username": username}, {"email": email}]})
    if existing_user:
        return JSONResponse(content={"message": "Username or email already taken"}, status_code=400)
    
    if role not in ["manager", "user"]:
        return JSONResponse(content={"message": "Invalid role"}, status_code=400)
    
    user_id = create_user(username, email, password, role)
    return JSONResponse(content={"message": "Registration successful", "user_id": user_id})

@app.get("/admindashboard")
async def admin_dashboard(request: Request):
    return templates.TemplateResponse("admindashboard.html", {"request": request})

@app.get("/userdashboard")
async def user_dashboard(request: Request):
    return templates.TemplateResponse("userdashboard.html", {"request": request})

@app.post("/create_task")
async def create_task(
    title: str = Form(...),
    description: str = Form(...),
    priority: str = Form(...),
    status: str = Form(...),
    due_date: str = Form(...),
    assigned_to: str = Form(...)
):
    print(f"Received task data: title={title}, description={description}, priority={priority}, status={status}, due_date={due_date}, assigned_to={assigned_to}")
    
    assigned_to_list = [user.strip() for user in assigned_to.split(',')]
    task = {
        "_id": str(ObjectId()),
        "title": title,
        "description": description,
        "priority": priority,
        "status": status,
        "dueDate": due_date,
        "assignedTo": assigned_to_list,
        "created_at": datetime.now().isoformat()
    }
    tasks_collection.insert_one(task)
    return JSONResponse(content={"message": "Task created successfully", "task_id": task["_id"]})

@app.get("/get_tasks")
async def get_tasks(
    search: str = None,
    priority: str = None,
    status: str = None,
    due_date: str = None,
    assigned_to: str = None
):
    print("assigned_to",assigned_to)
    query = {}
    if search:
        query["$or"] = [
            {"title": {"$regex": search, "$options": "i"}},
            {"description": {"$regex": search, "$options": "i"}}
        ]
    if priority:
        query["priority"] = priority
    if status:
        query["status"] = status
    if due_date:
        query["dueDate"] = due_date
    if assigned_to:
        query["assignedTo"] = assigned_to
    
    tasks = list(tasks_collection.find(query))
    for task in tasks:
        task["_id"] = str(task["_id"])
    return JSONResponse(content=tasks)

@app.put("/update_task/{task_id}")
async def update_task(
    task_id: str,
    task_data: dict = Body(...)
):
    updated_task = {
        "title": task_data.get("title"),
        "description": task_data.get("description"),
        "priority": task_data.get("priority"),
        "status": task_data.get("status"),
        "dueDate": task_data.get("dueDate"),
        "assignedTo": task_data.get("assignedTo")
    }
    result = tasks_collection.update_one({"_id": task_id}, {"$set": updated_task})
    if result.modified_count > 0:
        return JSONResponse(content={"message": "Task updated successfully"})
    else:
        return JSONResponse(content={"message": "Task not found"}, status_code=404)

@app.delete("/delete_task/{task_id}")
async def delete_task(task_id: str):
    result = tasks_collection.delete_one({"_id": task_id})
    if result.deleted_count > 0:
        return JSONResponse(content={"message": "Task deleted successfully"})
    else:
        return JSONResponse(content={"message": "Task not found"}, status_code=404)

@app.get("/get_users")
async def get_users():
    users = list(users_collection.find({}, {"_id": 1, "username": 1}))
    for user in users:
        user["_id"] = str(user["_id"])
    return JSONResponse(content=users)

@app.put("/update_task_status/{task_id}")
async def update_task_status(task_id: str, status: str):
    result = tasks_collection.update_one(
        {"_id": ObjectId(task_id)},
        {"$set": {"status": status}}
    )
    if result.modified_count > 0:
        # Notify admin (you can implement this part based on your notification system)
        return JSONResponse(content={"message": "Task status updated successfully"})
    else:
        return JSONResponse(content={"message": "Task not found"}, status_code=404)


 #Report generation
@app.post("/generate_report")
def generate_text_report():
    # Fetch tasks data
    in_progress_tasks = tasks_collection.find({"status": "In Progress"})
    completed_tasks = tasks_collection.find({"status": "Completed"})
    print("tasks completed vs progress", completed_tasks,in_progress_tasks)
    # Build the report
    report = []
    report.append("Task Report: In Progress vs Completed")
    report.append("=" * 40)
    
    # Add in-progress tasks
    report.append("\nIn Progress Tasks:")
    for task in in_progress_tasks:
        report.append(f"- Title: {task['title']}")
        report.append(f"  Assigned To: {task['assignedTo']}")
        report.append(f"  Priority: {task['priority']}")
        report.append(f"  Due Date: {task['dueDate']}")
        report.append("")
    
    # Add completed tasks
    report.append("\nCompleted Tasks:")
    for task in completed_tasks:
        report.append(f"- Title: {task['title']}")
        report.append(f"  Assigned To: {task['assignedTo']}")
        report.append(f"  Priority: {task['priority']}")
        report.append(f"  Due Date: {task['dueDate']}")
        report.append("")

    report_content = "\n".join(report)
    return JSONResponse(content={"message": "report generation completed", "report":report_content})

@app.post("/generate_task_report")
def generate_task_report():
    # Fetch tasks data
    in_progress_count = tasks_collection.count_documents({"status": "In Progress"})
    completed_count = tasks_collection.count_documents({"status": "Completed"})
    
    # Data for pie chart
    labels = ['In Progress', 'Completed']
    counts = [in_progress_count, completed_count]
    colors = ['skyblue', 'lightgreen']
    
    # Plot the pie chart
    plt.figure(figsize=(6, 6))
    plt.pie(counts, labels=labels, autopct='%1.1f%%', colors=colors, startangle=140)
    plt.title('Task Report: In Progress vs Completed')
    plt.axis('equal')  # Equal aspect ratio ensures the pie chart is circular.

    # Save the chart to a BytesIO buffer
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    plt.close()

    # Encode the image to base64
    image_base64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    buf.close()

    # Return the image as a base64 string
    return JSONResponse(content={
        "message": "Task report generated successfully",
        "chart": f"data:image/png;base64,{image_base64}"
    })


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

