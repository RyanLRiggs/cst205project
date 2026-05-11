"""
Name: Ryan, Andrew, Chris, Diego
Date: 2026-04-22
Course: CST 205 - Multimedia Programming
Final Project

A Flask app that lets you click on mood board and play music
based on the emotion you picked. Using spotify api to get playlist.
"""

import os
import secrets
import urllib.parse
from datetime import datetime, UTC
from pathlib import Path

import requests
from dotenv import load_dotenv
from flask import Flask, abort, redirect, render_template, request, session, url_for
from PIL import Image

from image_info import image_info

load_dotenv()

app = Flask(__name__, static_folder="images", static_url_path="/images")
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-change-me")

IMAGE_FOLDER = Path(app.static_folder)

# spotify stuff
CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:5000/callback")

AUTH_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"
API_BASE = "https://api.spotify.com/v1"

SCOPES = ["playlist-modify-private", "playlist-modify-public"]

# these are the search queries we use for each emotion
MOOD_SEEDS = {
    "happy": ["happy upbeat", "feel good pop", "sunny indie", "good vibes", "dance happy", "joyful hits"],
    "afraid": ["spooky ambient", "horror soundtrack", "dark cinematic", "eerie music", "scary atmospheric", "tense thriller"],
    "guilty": ["guilty conscience", "sad indie", "regret songs", "emotional acoustic", "moody alternative", "introspective pop"],
    "excited": ["hype music", "energetic pop", "pump up hits", "upbeat dance", "exciting anthems", "high energy"],
    "sorry": ["apology songs", "sad ballads", "sorry music", "emotional pop", "heartfelt acoustic", "soft sad"],
    "jealous": ["jealousy songs", "bitter pop", "dramatic rnb", "envious mood", "moody indie", "tension music"],
    "sad": ["sad acoustic", "melancholy indie", "heartbreak songs", "moody piano", "soft sad pop", "emotional ballads"],
    "proud": ["triumphant music", "feel good anthems", "victory songs", "empowerment pop", "proud moments", "celebration hits"],
    "tired": ["lofi beats", "calm ambient", "sleepy music", "chill study", "soft background", "relaxing instrumental"],
    "angry": ["angry rock", "rage workout", "heavy metal energy", "punk aggression", "intense gym music", "hardcore drive"],
    "bored": ["discover new music", "eclectic mix", "indie alternative", "interesting sounds", "quirky pop", "genre blending"],
    "loved": ["romantic love songs", "date night", "sensual rnb", "soft romantic pop", "candlelight jazz", "slow dance"],
    "embarrassed": ["awkward indie", "quirky pop", "lighthearted fun", "silly songs", "upbeat comedy", "feel better music"],
    "surprised": ["plot twist music", "unexpected beats", "eclectic pop", "surprising sounds", "wow moments", "dynamic music"],
    "shy": ["soft acoustic", "quiet indie", "gentle music", "shy vibes", "soft spoken", "introvert playlist"],
    "hopeful": ["hopeful anthems", "optimistic pop", "uplifting songs", "positive vibes", "inspiring music", "bright future"],
}


# returns the emotion dict that matches the id, or None
def get_emotion_by_id(emotion_id):
    for emotion in image_info:
        if emotion["id"] == emotion_id:
            return emotion
    return None


# uses pillow to get image info
def get_image_metadata(filename):
    image_path = IMAGE_FOLDER / filename

    if not image_path.exists():
        return None

    with Image.open(image_path) as img:
        return {
            "mode": img.mode,
            "format": img.format,
            "width": img.width,
            "height": img.height,
        }


# builds the url to send user to spotify login
def get_spotify_auth_url():
    state = secrets.token_urlsafe(16)
    session["oauth_state"] = state

    params = {
        "client_id": CLIENT_ID,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": " ".join(SCOPES),
        "state": state,
        "show_dialog": "true",
    }
    return f"{AUTH_URL}?{urllib.parse.urlencode(params)}"


# trades the code spotify gives us for an actual access token
def get_token_from_code(code):
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    resp = requests.post(TOKEN_URL, data=data, headers=headers, timeout=20)

    print("token exchange status:", resp.status_code)

    resp.raise_for_status()
    return resp.json()


def do_token_refresh(refresh_token):
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    resp = requests.post(TOKEN_URL, data=data, headers=headers, timeout=20)
    resp.raise_for_status()
    return resp.json()


def get_current_time():
    return datetime.now(UTC).timestamp()


def check_if_token_expired():
    expires_at = session.get("expires_at", 0)
    return get_current_time() >= expires_at


# gets a valid token, refreshes it if expired
def get_token():
    token = session.get("access_token")
    refresh_tok = session.get("refresh_token")

    if not token:
        return None

    # if not expired just return it
    if not check_if_token_expired():
        return token

    if not refresh_tok:
        return None

    # refresh it
    new_tokens = do_token_refresh(refresh_tok)
    session["access_token"] = new_tokens["access_token"]
    session["expires_at"] = get_current_time() + new_tokens.get("expires_in", 3600) - 60

    if "refresh_token" in new_tokens:
        session["refresh_token"] = new_tokens["refresh_token"]

    return session["access_token"]


# helper to make GET requests to spotify api
def spotify_get(endpoint, token, params=None):
    url = API_BASE + endpoint
    headers = {"Authorization": "Bearer " + token}
    resp = requests.get(url, headers=headers, params=params, timeout=20)
    print("spotify GET", endpoint, resp.status_code)
    resp.raise_for_status()
    return resp.json()


# helper to make POST requests to spotify api
def spotify_post(endpoint, token, body):
    url = API_BASE + endpoint
    headers = {
        "Authorization": "Bearer " + token,
        "Content-Type": "application/json",
    }
    resp = requests.post(url, headers=headers, json=body, timeout=20)
    print("spotify POST", endpoint, resp.status_code)
    resp.raise_for_status()
    if resp.text:
        return resp.json()
    return {}


def get_user_profile(token):
    return spotify_get("/me", token)


# searches spotify for tracks matching a query
def search_spotify(token, query, market="US"):
    data = spotify_get("/search", token, params={
        "q": query,
        "type": "track",
        "limit": 10,
        "market": market
    })
    return data.get("tracks", {}).get("items", [])


# higher popularity + matching keywords = better score
def score_track(track, mood, query):
    score = track.get("popularity", 0)

    name = track.get("name", "").lower()
    artists = ""
    for a in track.get("artists", []):
        artists += a.get("name", "") + " "
    artists = artists.lower()

    # keywords that match the mood
    keywords = {
        "happy": ["happy", "sun", "smile", "good", "dance", "joy"],
        "afraid": ["fear", "dark", "spooky", "eerie", "horror", "scary"],
        "guilty": ["guilty", "regret", "sorry", "blame", "shame"],
        "excited": ["hype", "energy", "excited", "pump", "go", "fire"],
        "sorry": ["sorry", "apology", "forgive", "hurt", "sad"],
        "jealous": ["jealous", "envy", "bitter", "want", "wish"],
        "sad": ["sad", "blue", "cry", "alone", "heart", "tears"],
        "proud": ["proud", "win", "triumph", "strong", "rise"],
        "tired": ["sleep", "rest", "lofi", "calm", "slow", "chill"],
        "angry": ["rage", "fire", "power", "hard", "fight", "run"],
        "bored": ["new", "different", "quirky", "indie", "eclectic"],
        "loved": ["love", "romance", "kiss", "heart", "slow", "night"],
        "embarrassed": ["awkward", "silly", "oops", "laugh", "fun"],
        "surprised": ["wow", "unexpected", "twist", "dynamic", "wild"],
        "shy": ["soft", "quiet", "gentle", "small", "whisper"],
        "hopeful": ["hope", "bright", "rise", "new", "positive", "dream"],
    }

    for word in keywords.get(mood, []):
        if word in name or word in artists or word in query.lower():
            score += 15

    return score


# gets a list of tracks for the mood
def get_tracks_for_mood(token, mood, extra, count, market="US"):
    queries = list(MOOD_SEEDS.get(mood, []))

    # add extra stuff the user typed in
    if extra:
        queries.append(mood + " " + extra)
        queries.append(extra)
        queries.append(extra + " soundtrack")

    seen = {}  # track id -> track dict, so no duplicates

    for q in queries:
        results = search_spotify(token, q, market)
        for t in results:
            tid = t.get("id")
            if not tid:
                continue

            name = t.get("name")
            uri = t.get("uri")
            if not name or not uri:
                continue

            artist_names = ", ".join(a.get("name", "") for a in t.get("artists", []))

            track_data = {
                "id": tid,
                "uri": uri,
                "name": name,
                "artists": artist_names,
                "popularity": t.get("popularity", 0),
                "url": t.get("external_urls", {}).get("spotify"),
                "score": score_track(t, mood, q)
            }

            # keep the one with higher score if we already have it
            if tid not in seen or track_data["score"] > seen[tid]["score"]:
                seen[tid] = track_data

    # sort by score and return top N
    all_tracks = list(seen.values())
    all_tracks.sort(key=lambda x: x["score"], reverse=True)
    return all_tracks[:count]


# --- routes ---

@app.route("/")
def index():
    # get image metadata using happy.png as a sample (like hw4)
    metadata = get_image_metadata("happy.png")

    if metadata is None:
        abort(404)

    logged_in = get_token() is not None

    return render_template("index.html",
        emotions=image_info,
        metadata=metadata,
        logged_in=logged_in
    )


@app.route("/emotion/<emotion_id>")
@app.route("/detail/<emotion_id>")
def detail(emotion_id):
    emotion = get_emotion_by_id(emotion_id)

    if emotion is None:
        abort(404)

    # get metadata for this emotion's image
    metadata = get_image_metadata(emotion_id + ".png")

    if metadata is None:
        abort(404)

    logged_in = get_token() is not None

    return render_template("detail.html",
        emotion=emotion,
        metadata=metadata,
        logged_in=logged_in
    )


@app.route("/login")
def login():
    if not CLIENT_ID or not CLIENT_SECRET:
        return "Error: missing spotify credentials, check your .env file", 500
    return redirect(get_spotify_auth_url())


@app.route("/callback")
def callback():
    # spotify redirects here after user logs in
    err = request.args.get("error")
    if err:
        return "Spotify login failed: " + err, 400

    code = request.args.get("code")
    state = request.args.get("state")

    # prevents CSRF
    if not code or state != session.get("oauth_state"):
        return "Something went wrong with login, try again", 400

    tokens = get_token_from_code(code)
    session["access_token"] = tokens["access_token"]
    session["refresh_token"] = tokens.get("refresh_token")
    session["expires_at"] = get_current_time() + tokens.get("expires_in", 3600) - 60

    # if they were on an emotion page before logging in, send them back
    next_page = session.pop("next_emotion", None)
    if next_page:
        return redirect(url_for("detail", emotion_id=next_page))

    return redirect(url_for("index"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


@app.route("/generate/<emotion_id>", methods=["POST"])
def generate(emotion_id):
    token = get_token()

    # send them to login if not connected
    if not token:
        session["next_emotion"] = emotion_id
        return redirect(url_for("login"))

    emotion = get_emotion_by_id(emotion_id)
    if emotion is None:
        abort(404)

    # get form data
    playlist_name = request.form.get("playlist_name", "").strip()
    extra = request.form.get("extra_prompt", "").strip()
    is_public = request.form.get("is_public", "false") == "true"

    try:
        num_tracks = int(request.form.get("track_count", "20"))
        # min 5 and max 50
        if num_tracks < 5:
            num_tracks = 5
        if num_tracks > 50:
            num_tracks = 50
    except:
        num_tracks = 20

    # use emotion id as mood, fall back to happy if somehow not in our list
    mood = emotion_id
    if mood not in MOOD_SEEDS:
        mood = "happy"

    # get user country so results are available in their region
    profile = get_user_profile(token)
    market = profile.get("country", "US")

    print(f"generating playlist for mood={mood}, tracks={num_tracks}, market={market}")

    tracks = get_tracks_for_mood(token, mood, extra, num_tracks, market)

    if not tracks:
        return render_template("result.html",
            error="Couldn't find any songs for that mood. Try something else!"
        )

    # set a default playlist name if they left it blank
    if not playlist_name:
        playlist_name = emotion["title"] + " Mood Mix"
        if extra:
            playlist_name += " - " + extra[:30]

    desc = "Made with Mood Music app - CST 205 Final Project"
    if extra:
        desc += " | vibe: " + extra

    # create the playlist on spotify
    new_playlist = spotify_post("/me/playlists", token, {
        "name": playlist_name,
        "description": desc,
        "public": is_public
    })

    playlist_id = new_playlist["id"]
    playlist_url = new_playlist.get("external_urls", {}).get("spotify")

    # add all the tracks
    uris = [t["uri"] for t in tracks]
    spotify_post("/playlists/" + playlist_id + "/items", token, {"uris": uris})

    print("done! playlist created:", playlist_name)

    return render_template("result.html",
        playlist_name=playlist_name,
        playlist_url=playlist_url,
        tracks=tracks,
        mood=emotion["title"],
        extra_prompt=extra,
        public=is_public
    )


if __name__ == "__main__":
    app.run(debug=True)
