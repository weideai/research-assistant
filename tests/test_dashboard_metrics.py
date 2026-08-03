"""Guard the dashboard metric cards as entries rather than decoration.

Two failures here are silent. A card can stop being a link and still look
identical, and a link can carry a query parameter its route ignores — which
renders a full list that reads as a broken filter. Both need a test because
neither shows up in a diff or in the rendered page.
"""

import re
from pathlib import Path

import pytest

TEMPLATE = Path(__file__).resolve().parent.parent / "app" / "templates" / "dashboard.html"
METRIC_COUNT = 4


def _metric_tags():
    """Every element carrying the .wb-stat class, with its tag name."""
    html = TEMPLATE.read_text(encoding="utf-8")
    # `wb-stat` must be a whole class token: `wb-stats` is the wrapper, not a card.
    return re.findall(r'<(\w+)\s+class="wb-stat(?:\s[^"]*)?"([^>]*)>', html)


def test_every_metric_card_is_a_link():
    """design.md E4: a static figure nobody can act on is wasted first-screen height."""
    tags = _metric_tags()
    assert len(tags) == METRIC_COUNT, f"预期 {METRIC_COUNT} 张指标卡，实际 {len(tags)}"
    non_links = [tag for tag, _ in tags if tag != "a"]
    assert not non_links, (
        f"以下指标卡不是链接：{non_links}。CSS 里的 a.wb-stat 规则会静默失效，"
        f"卡片看起来一样但点不动。"
    )


def test_every_metric_link_has_a_destination():
    tags = _metric_tags()
    without_href = [attrs.strip()[:60] for _, attrs in tags if "href=" not in attrs]
    assert not without_href, "以下指标卡缺少 href：" + ", ".join(without_href)


@pytest.mark.parametrize("param,route_func", [
    ("status", "samples"),
    ("status", "tasks"),
    ("status", "experiments"),
])
def test_routes_read_the_query_params_the_metrics_pass(param, route_func):
    """A link with ?status=... to a route that ignores it returns everything.

    That is worse than no filter: the page claims to be filtered and is not.
    """
    source = (Path(__file__).resolve().parent.parent / "app" / "main.py").read_text(encoding="utf-8")
    match = re.search(rf"\ndef {route_func}\(\):(.*?)(?=\n@bp\.route)", source, re.S)
    assert match, f"未找到路由 {route_func}，可能已改名"
    assert f'request.args.get("{param}"' in match.group(1), (
        f"路由 {route_func} 没有读取 {param} 参数，但仪表盘的链接会传它 —— "
        f"结果是返回全部数据，看起来像筛选坏了"
    )


def test_samples_status_filter_actually_narrows_the_list(client, auth):
    """The static checks above cannot prove the filter reaches the query."""
    auth.register()
    for code, status in (("S-OK", "可用"), ("S-BAD", "异常")):
        client.post("/samples", data={"sample_code": code, "status": status}, follow_redirects=True)

    unfiltered = client.get("/samples").get_data(as_text=True)
    assert "S-OK" in unfiltered and "S-BAD" in unfiltered

    filtered = client.get("/samples?status=可用").get_data(as_text=True)
    assert "S-OK" in filtered, "状态筛选把匹配的样本也过滤掉了"
    assert "S-BAD" not in filtered, "状态筛选没有生效，异常样本仍然出现在结果里"
