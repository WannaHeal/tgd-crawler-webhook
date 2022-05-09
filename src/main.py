import os
from dataclasses import dataclass
from pathlib import Path
from typing import List
from urllib.parse import urljoin

from bs4 import BeautifulSoup
import requests

WEBHOOK_URL = os.environ.get("WEBHOOK_URL")
STREAMER_USERNAME = os.environ.get("STREAMER_USERNAME")
IGNORED_CATEGORIES = os.environ.get("IGNORED_CATEGORIES", "")


@dataclass
class TgdPost:
    post_id: int
    category: str
    title: str
    url: str


def test_webhook_url(webhook_url: str):
    r = requests.get(webhook_url)
    if not r.ok:
        raise ValueError("Environment variable WEBHOOK_URL not proper")


def get_posts_from_tdg(streamer_username: str) -> str:
    r = requests.get(urljoin("https://tgd.kr", streamer_username))
    if not r.ok:
        raise ValueError("page not ok")
    return r.text


def parse_posts(html_body: str) -> List[TgdPost]:
    ret = []

    soup = BeautifulSoup(html_body, "lxml")
    posts = soup.select("div.article-list-row")

    for post in posts:
        # Exclude featured posts
        if "featured" in post.attrs["class"]:
            continue

        # print(type(post))
        # print(post)
        # print("글 번호:", post.get("id", "").split("-")[-1])
        if "notice" in post.attrs["class"]:
            cat = "공지사항"
        else:
            cat = post.select_one(".category").string
        # print("카테고리:", cat)
        a = post.a
        # print("제목:", a.attrs["title"])
        # print("링크:", "https://tgd.kr" + a.attrs["href"])
        # print("====================")
        ret.append(TgdPost(
            post_id=int(post.get("id", "").split("-")[-1]),
            category=cat,
            title=a.attrs["title"],
            url=urljoin("https://tgd.kr", a.attrs["href"]),
        ))

    # print(ret)
    return ret[::-1]


def filter_sent_posts(l: List[TgdPost]) -> List[TgdPost]:
    ret = []
    file = Path("sent.txt")
    if not file.exists():
        with file.open("x", encoding="UTF-8") as f:
            pass

    with file.open("r", encoding="UTF-8") as f:
        sent_posts = set(map(int, [line.rstrip() for line in f]))
    with file.open("a", encoding="UTF-8") as f:
        for post in l:
            if post.post_id in sent_posts:
                continue
            ret.append(post)
            f.write(str(post.post_id) + "\n")
    return ret

def filter_posts_with_ignored_categories(l: List[TgdPost]) -> List[TgdPost]:
    ret = []
    ignored_categories = IGNORED_CATEGORIES.split(",")

    for post in l:
        if post.category in ignored_categories:
            continue
        ret.append(post)
    return ret


def upload_new_posts(l: List[TgdPost]):
    payload = {}
    payload["content"] = "트게더에 새로운 글이 올라왔어요!"
    payload["embeds"] = []

    for i, post in enumerate(l):
        embed = {}
        embed["title"] = f"[{post.category}] {post.title}"
        embed["type"] = "rich"
        embed["url"] = post.url
        payload["embeds"].append(embed)
        if i % 10 == 9:
            res = requests.post(WEBHOOK_URL, json=payload)
            if not res.ok:
                raise RuntimeError(f"Something is wrong: {res.text}")
            payload["embeds"].clear()
    
    if len(payload["embeds"]) != 0:
        res = requests.post(WEBHOOK_URL, json=payload)
        if not res.ok:
            raise RuntimeError(f"Something is wrong: {res.text}")


if __name__ == "__main__":
    if WEBHOOK_URL is None:
        raise ValueError("Environment variable WEBHOOK_URL not set")
    if STREAMER_USERNAME is None:
        raise ValueError("Environment variable STREAMER_NAME not set")


    body = get_posts_from_tdg(STREAMER_USERNAME)
    posts = parse_posts(body)
    posts = filter_sent_posts(posts)
    posts = filter_posts_with_ignored_categories(posts)
    upload_new_posts(posts)
