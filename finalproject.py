"""
Name: Ryan, Andrew, Chris, Diego
Date: 2026-04-22
Course: CST 205 - Multimedia Programming
Final Project

A Flask app that lets you click on mood board and play music
based on the emotion you picked. Using spotify api to get playlist.
"""

from pathlib import Path

from flask import Flask, abort, render_template
from flask_bootstrap import Bootstrap5
from PIL import Image

from image_info import image_info

app = Flask(__name__, static_folder="images", static_url_path="/images")
bootstrap = Bootstrap5(app)

IMAGE_FOLDER = Path(app.static_folder)


def get_emotion_by_id(emotion_id):
    """Return the dictionary for one emotion, or None if it does not exist."""
    for emotion in image_info:
        if emotion["id"] == emotion_id:
            return emotion
    return None


def get_image_metadata(filename):
    """Return basic image information using Pillow."""
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


@app.route("/")
def index():
    metadata = get_image_metadata("emotions.png")

    if metadata is None:
        abort(404)

    return render_template(
        "index.html",
        emotions=image_info,
        metadata=metadata,
    )


@app.route("/emotion/<emotion_id>")
@app.route("/detail/<emotion_id>")
def detail(emotion_id):
    emotion = get_emotion_by_id(emotion_id)

    if emotion is None:
        abort(404)

    metadata = get_image_metadata(f"{emotion_id}.png")

    if metadata is None:
        abort(404)

    return render_template(
        "detail.html",
        emotion=emotion,
        metadata=metadata,
    )


if __name__ == "__main__":
    app.run(debug=True)