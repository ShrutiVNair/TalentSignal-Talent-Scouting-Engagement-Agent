# TalentSignal AI

TalentSignal AI is an AI-powered recruiting assistant that helps recruiters move from a job description to a ranked candidate shortlist with **explainable match scoring** and **simulated candidate engagement**.

Instead of just finding candidates, TalentSignal estimates **how interested they actually are**, enabling better and faster hiring decisions.

---

## 🎯 Problem

Recruiters spend hours:
- searching for candidates  
- manually evaluating resumes  
- sending outreach messages  
- waiting for replies  

Even after all this, they still don’t know:
👉 *Who is actually interested?*

---

## 💡 Solution

TalentSignal AI automates the entire workflow:

```text
Job Description
→ Candidate Discovery
→ Match Scoring (Explainable)
→ Simulated Outreach
→ Interest Scoring
→ Ranked Shortlist
→ HR Decision Recommendation
````

---

## ⚙️ Key Features

### 🔍 1. Job Description Parsing

* Upload or paste JD (TXT, PDF, DOCX)
* Extract:

  * role title
  * required skills
  * experience
  * work mode/location

---

### 🧠 2. Candidate Matching (Explainable)

* Scores candidates based on:

  * skills match
  * experience
  * domain relevance
  * work mode fit
* Provides **clear reasoning for each score**

---

### 💬 3. Simulated Candidate Engagement

* Automatically generates outreach messages
* Simulates candidate replies
* Analyzes:

  * sentiment
  * interest signals
  * objections

---

### 📊 4. Interest Scoring

* Estimates candidate interest from simulated responses
* Avoids waiting for real email replies
* Makes shortlist more realistic

---

### 🏆 5. Ranked Shortlist

Candidates are ranked using:

```text
Combined Score = 0.65 × Match Score + 0.35 × Interest Score
```

Each candidate includes:

* Match Score
* Interest Score
* Combined Score
* Explanation
* Conversation summary
* Recommended HR action

---

### 🧾 6. HR Decision Summary

Provides a clear recommendation:

* Schedule recruiter screen
* Send role details
* Recruiter review
* Keep warm
* Do not contact

---

### 💌 7. Email Demo (Optional)

* Generate outreach email draft
* Send test email safely
* Does NOT send to real candidates in demo mode

---

## 🖥️ Demo Flow

```text
Paste or upload JD
→ Parse JD
→ Run Talent Scan
→ View ranked candidates
→ Simulate outreach
→ See interest scores
→ Review HR recommendation
```

---

## 🏗️ Tech Stack

* **Frontend**: Streamlit
* **Backend**: Python
* **Database**: SQLite
* **AI Logic**: Custom scoring + simulation
* **Document Parsing**: PyPDF2, python-docx

---

## 🚀 Running Locally

```bash
git clone https://github.com/YOUR_USERNAME/talentsignal-ai
cd talentsignal-ai
pip install -r requirements.txt
streamlit run app.py
```

---

## 🌐 Live Demo

👉 [Your deployed Streamlit URL]

---

## 📦 Project Files

👉 [[Google Drive ZIP link]](https://drive.google.com/drive/folders/1tNNVP1-LPJmiLYTHkhN5ToZAx-g0ibmK?usp=sharing)

---

## 🧠 Why This Matters

TalentSignal AI shifts recruiting from:
❌ static resume screening
❌ guess-based outreach

To:
✅ data-driven decision making
✅ interest-aware candidate ranking

---

## 🔮 Future Improvements

* real-time email + reply ingestion
* LinkedIn/ATS integrations
* LLM-based conversation generation
* automated scheduling

---

## 👤 Author

Your Name
GitHub: [https://github.com/YOUR_USERNAME](https://github.com/ShrutiVNair)
