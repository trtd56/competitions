import os
import threading

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from competitions.info import CompetitionInfo
from competitions.leaderboard import Leaderboard
from competitions.runner import JobRunner
from competitions.submissions import Submissions


HF_TOKEN = os.environ.get("HF_TOKEN", None)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
COMPETITION_ID = os.getenv("COMPETITION_ID")
OUTPUT_PATH = os.getenv("OUTPUT_PATH", "/tmp/model")
COMP_INFO = CompetitionInfo(competition_id=COMPETITION_ID, autotrain_token=HF_TOKEN)


class User(BaseModel):
    user_token: str


def run_job_runner():
    job_runner = JobRunner(token=HF_TOKEN, competition_info=COMP_INFO, output_path=OUTPUT_PATH)
    job_runner.run()


thread = threading.Thread(target=run_job_runner)
thread.start()


app = FastAPI()
static_path = os.path.join(BASE_DIR, "static")
app.mount("/static", StaticFiles(directory=static_path), name="static")
templates_path = os.path.join(BASE_DIR, "templates")
templates = Jinja2Templates(directory=templates_path)


@app.get("/", response_class=HTMLResponse)
async def read_form(request: Request):
    """
    This function is used to render the HTML file
    :param request:
    :return:
    """
    if HF_TOKEN is None:
        return templates.TemplateResponse("error.html", {"request": request})
    context = {
        "request": request,
        "logo": COMP_INFO.logo_url,
        "competition_type": COMP_INFO.competition_type,
    }
    return templates.TemplateResponse("index.html", context)


@app.get("/competition_info", response_class=JSONResponse)
async def get_comp_info(request: Request):
    info = COMP_INFO.competition_desc
    # info = markdown.markdown(info)
    resp = {"response": info}
    return resp


@app.get("/dataset_info", response_class=JSONResponse)
async def get_dataset_info(request: Request):
    info = COMP_INFO.dataset_desc
    # info = markdown.markdown(info)
    resp = {"response": info}
    return resp


@app.get("/leaderboard/{lb}", response_class=JSONResponse)
async def get_leaderboard(request: Request, lb: str):
    leaderboard = Leaderboard(
        end_date=COMP_INFO.end_date,
        eval_higher_is_better=COMP_INFO.eval_higher_is_better,
        max_selected_submissions=COMP_INFO.selection_limit,
        competition_id=COMPETITION_ID,
        autotrain_token=HF_TOKEN,
    )
    df = leaderboard.fetch(private=lb == "private")
    resp = {"response": df.to_markdown(index=False)}
    return resp


@app.post("/my_submissions", response_class=JSONResponse)
async def my_submissions(request: Request, user: User):
    sub = Submissions(
        end_date=COMP_INFO.end_date,
        submission_limit=COMP_INFO.submission_limit,
        competition_id=COMPETITION_ID,
        token=HF_TOKEN,
    )
    success_subs, failed_subs = sub.my_submissions(user.user_token)
    success_subs = success_subs.to_markdown(index=False)
    failed_subs = failed_subs.to_markdown(index=False)
    if len(success_subs.strip()) == 0 and len(failed_subs.strip()) == 0:
        success_subs = "You have not made any submissions yet."
        failed_subs = ""
    resp = {"response": {"success": success_subs, "failed": failed_subs}}
    return resp


@app.post("/new_submission", response_class=JSONResponse)
async def new_submission(
    submission_file: UploadFile = File(...),
    hub_model: str = Form(...),
    token: str = Form(...),
    submission_comment: str = Form(...),
):
    sub = Submissions(
        end_date=COMP_INFO.end_date,
        submission_limit=COMP_INFO.submission_limit,
        competition_id=COMPETITION_ID,
        token=HF_TOKEN,
    )
    if COMP_INFO.competition_type == "generic":
        resp = sub.new_submission(token, submission_file, submission_comment)
        return {"response": f"Success! You have {resp} submissions remaining today."}
    elif COMP_INFO.competition_type == "code":
        resp = sub.new_submission(token, hub_model, submission_comment)
        return {"response": f"Success! You have {resp} submissions remaining today."}
    return {"response": "Invalid competition type"}
