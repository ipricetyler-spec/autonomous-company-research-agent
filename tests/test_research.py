from research_agent.research import html_to_text


def test_html_to_text_removes_scripts_styles_and_tags() -> None:
    page = "<style>.secret{}</style><h1>Company</h1><script>ignore()</script><p>Profile</p>"
    assert html_to_text(page) == "Company Profile"

