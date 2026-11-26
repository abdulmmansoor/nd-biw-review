# ND Business and Innovation Watch - review version

A separate copy of the dashboard for reviewers, behind a review password. It is built from the project in
`..\ND Business and Innovation Watch` by `Build_Review_Version.bat` and does not change the project. Do not edit files
here except `review_settings.toml`: a refresh replaces everything else.

- Site address (send this to reviewers): https://nd-biw-review-meous7mytvf6esqrnzwgrp.streamlit.app/
  (Streamlit Community Cloud, account `abdulmmansoor`). The Fiscal and Economic Watch review is a different site:
  its address is in that review copy's README (not here, because this repository is public).
- App entry point: `ND_BIW/dashboard/app.py`
- Comments: the "Comment on this page" button opens the Microsoft Form set in `review_settings.toml`.
- Data: the results as of the last refresh (see "Data as of" on each page). The site does not update itself.
- The Business survey page shows made-up test data until the survey is fielded; the page says so. Once the survey
  tables hold real results the build stops before uploading, unless `publish_real_survey = true` is set in
  `review_settings.toml`.

Run it on this computer: `Start_Review_Locally.bat`, then open http://localhost:8542.

## Set up sharing (once)

1. **Comment form** (forms.office.com, UND sign-in)
   - New Form: "ND Business and Innovation Watch - review comments".
   - Questions: *Page* (text, required), *Comment* (text, long answer, required), *Name and organization* (text).
   - Settings: choose who can respond (anyone, or only people in your organization).
   - ... (More options) > **Get pre-filled URL** > type `PAGE` in the Page question > **Get pre-filled URL** > Copy.
   - Paste the link into `review_settings.toml` as `form_url = "..."`.
2. **GitHub** (github.com): the **public** repository `nd-biw-review`. Anyone can read its code and tables without
   the review password, so treat every upload as publishing. First time, connect and upload:
   `git remote add origin https://github.com/abdulmmansoor/nd-biw-review.git` then `git push -u origin main`.
   This dashboard uses the GitHub account `abdulmmansoor`, on Streamlit too; the builder stops if the copy points elsewhere.
3. **Review password**: run `Set_Review_Password.bat` in the project folder. Type a password, or press Enter to get a
   random one. It prints a `[review]` block with a salted hash; the password itself is not saved anywhere.
4. **Streamlit Community Cloud** (share.streamlit.io): Create app > from GitHub repository.
   - Sign in with GitHub as `abdulmmansoor`. Repository `abdulmmansoor/nd-biw-review`, branch `main`, main file `ND_BIW/dashboard/app.py`.
   - Advanced settings: the newest Python version offered; in **Secrets**, paste the `[review]` block.
   - Choose an app address, then Deploy. Community Cloud allows one private app per workspace (ND Fiscal and Economic
     Watch uses it), so this app is public; its pages are behind
     the review password. Without the `[review]` secret the site stays closed.
5. **Invite reviewers**: email them the app address and the review password. Anyone with both can open the draft;
   to cut off access, run `Set_Review_Password.bat` again and replace the secret (app > Settings > Secrets).

## Refresh it

Run `Build_Review_Version.bat` in the project folder after updating the project. It rebuilds this copy and asks
before uploading. Streamlit Cloud picks up the upload within a minute or two.
