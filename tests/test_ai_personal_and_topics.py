"""AI Jana: exact answers from the asker's own records, and the wider knowledge base."""

import pytest


def ask(client, headers, question, language="ru"):
    res = client.post(
        "/api/v1/ai/chat",
        json={"question": question},
        headers={**headers, "Accept-Language": language},
    )
    assert res.status_code == 200, res.text
    return res.json()


def test_own_leave_balance_comes_from_the_askers_profile(client, employee_headers):
    profile = client.get("/api/v1/me/profile", headers=employee_headers).json()
    data = ask(client, employee_headers, "Сколько у меня дней отпуска?")
    assert data["answer_status"] in {"personal", "grounded"}
    assert f"Остаток отпуска: {profile['leave_balance_days']:g} дн." in data["answer"]
    assert "Ближайший отпуск:" in data["answer"]


@pytest.mark.parametrize(
    "question,language,expected",
    [
        ("Что с моими заявками?", "ru", "Последние заявки:"),
        ("Какие курсы мне назначены?", "ru", "Назначенные курсы:"),
        ("Кто мой руководитель?", "ru", "Ваш руководитель: Тимур Касымов."),
        ("Когда ближайший праздник?", "ru", "Ближайшие праздники"),
        ("Менің өтініштерім қандай?", "kk", "Соңғы өтініштер:"),
        ("Демалыс күндерім қанша?", "kk", "Демалыс қалдығы:"),
        ("What is my leave balance?", "en", "Leave balance:"),
    ],
)
def test_personal_questions_get_exact_own_facts(
    client, employee_headers, question, language, expected
):
    data = ask(client, employee_headers, question, language)
    assert data["answer_status"] != "fallback", data
    assert expected in data["answer"]


def test_personal_answers_never_include_another_employees_records(client, employee_headers):
    mine = ask(client, employee_headers, "Что с моими заявками?")["answer"]
    assert "REQ-1044" not in mine  # Dana's request
    other = ask(client, employee_headers, "Что с заявками Даны?")
    assert other["answer_status"] == "unauthorized"


def test_how_to_questions_stay_knowledge_answers(client, employee_headers):
    data = ask(client, employee_headers, "Как оформить отпуск?")
    assert data["answer_status"] == "grounded"
    assert "По вашим данным" not in data["answer"]


@pytest.mark.parametrize(
    "question,language,section",
    [
        (
            "Как оформить декретный отпуск?",
            "ru",
            "Отпуск по беременности и родам и по уходу за ребёнком",
        ),
        ("Входят ли выходные в отпуск?", "ru", "Праздники и подсчёт дней отпуска"),
        ("Как оформить командировку?", "ru", "Командировки"),
        ("Как получить справку с места работы?", "ru", "Справки с места работы"),
        ("Сколько часов сверхурочной работы можно?", "ru", "Сверхурочная работа"),
        ("Как уволиться по собственному желанию?", "ru", "Увольнение по собственному желанию"),
        ("Как изменить телефон в профиле?", "ru", "Изменение контактных данных"),
        ("Іссапарға қалай барамын?", "kk", "Іссапарлар"),
        (
            "Декреттік демалыс қалай рәсімделеді?",
            "kk",
            "Жүктілік пен босануға және бала күтіміне арналған демалыс",
        ),
        ("How do I get an employment certificate?", "en", "Employment Certificates"),
    ],
)
def test_new_topics_are_answered_from_approved_sources(
    client, employee_headers, question, language, section
):
    data = ask(client, employee_headers, question, language)
    assert data["answer_status"] == "grounded", data
    assert section in [s["section_title"] for s in data["sources"]]


def test_reseeding_an_existing_demo_database_adds_the_topics_once(db_session):
    from app.models.knowledge import KnowledgeDocument
    from app.seed import seed_database
    from app.seed_hr_topics import TITLE

    seed_database(db_session)
    assert db_session.query(KnowledgeDocument).filter_by(title=TITLE).count() == 1
