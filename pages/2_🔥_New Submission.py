import uuid

import streamlit as st
from huggingface_hub import HfApi

import config
import utils

SUBMISSION_TEXT = f"""You can make upto {config.competition_info.submission_limit} submissions per day.
The test data has been divided into public and private splits.
Your score on the public split will be shown on the leaderboard.
Your final score will be based on your private split performance.
The final rankings will be based on the private split performance.
"""

SUBMISSION_ERROR = """Submission is not in a proper format.
Please check evaluation instructions for more details."""


def app():
    st.set_page_config(page_title="New Submissions", page_icon="🤗")
    st.write("## New Submission")
    st.markdown(SUBMISSION_TEXT)
    uploaded_file = st.file_uploader("Choose a file")
    # user token
    user_token = st.text_input("Enter your Hugging Face token", value="", type="password")
    user_token = user_token.strip()
    # add submit button
    submit_button = st.button("Submit")
    if uploaded_file is not None and user_token != "" and submit_button:
        # verify token
        user_info = utils.user_authentication(token=user_token)
        if "error" in user_info:
            st.error("Invalid token")
            return

        if user_info["emailVerified"] is False:
            st.error("Please verify your email on Hugging Face Hub")
            return

        # check if user can submit to the competition
        if utils.check_user_submission_limit(user_info) is False:
            st.error("You have reached your submission limit for today")
            return

        bytes_data = uploaded_file.getvalue()
        # verify file is valid
        if not utils.verify_submission(bytes_data):
            st.error("Invalid submission")
            st.write(SUBMISSION_ERROR)
            # write a horizontal html line
            st.markdown("<hr/>", unsafe_allow_html=True)
        else:
            with st.spinner("Creating submission... Please wait"):
                user_id = user_info["id"]
                submission_id = str(uuid.uuid4())
                file_extension = uploaded_file.name.split(".")[-1]
                # upload file to hf hub
                api = HfApi()
                api.upload_file(
                    path_or_fileobj=bytes_data,
                    path_in_repo=f"submissions/{user_id}-{submission_id}.{file_extension}",
                    repo_id=config.COMPETITION_ID,
                    repo_type="dataset",
                    token=config.AUTOTRAIN_TOKEN,
                )
                # update submission limit
                submissions_made = utils.increment_submissions(
                    user_id=user_id,
                    submission_id=submission_id,
                    submission_comment="",
                )
                # schedule submission for evaluation
                utils.create_project(
                    project_id=f"{submission_id}",
                    dataset=f"{config.COMPETITION_ID}",
                    submission_dataset=user_id,
                    model="generic_competition",
                )
            st.success("Submission scheduled for evaluation")
            st.success(f"You have {config.SUBMISSION_LIMIT - submissions_made} submissions left for today.")


if __name__ == "__main__":
    app()
