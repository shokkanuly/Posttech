import json

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.ai_rules import AssistantRules, load_assistant_rules
from app.config import settings
from app.knowledge_files import PolicyBundle, import_bundle, read_bundle
from app.models.enums import UserRole
from app.models.knowledge import KnowledgeDocument
from app.models.user import User
from app.retrieval_ranker import FEATURE_NAMES, RelevanceModel, load_relevance_model
from ml.data import ROOT, QueryExample, RetrievalQuery, load_corpus, validate_splits, write_json
from ml.retrieval import predict


@pytest.fixture
def bundle():
    return read_bundle(ROOT / "knowledge/documents/vacation.json")


@pytest.fixture
def accepting_model(tmp_path):
    model = RelevanceModel(
        schema_version=1,
        feature_names=FEATURE_NAMES,
        coefficients=[10, 0, 0, 0],
        intercept=-5,
        threshold=0.5,
        training_manifest={"purpose": "test-only"},
    )
    path = tmp_path / "ranker.json"
    write_json(path, model.model_dump())
    return path


def test_rule_files_schemas_and_dataset_are_consistent():
    assert len(load_assistant_rules().rules) == 12
    corpus = load_corpus()
    assert len(corpus) == 16
    splits = validate_splits(ROOT / "ml/data", corpus)
    assert {key: len(rows) for key, rows in splits.items()} == {
        "train": 58,
        "validation": 20,
        "test": 22,
    }
    for path, model in [
        ("knowledge/assistant_rules.schema.json", AssistantRules),
        ("knowledge/policy_bundle.schema.json", PolicyBundle),
        ("ml/data/query.schema.json", QueryExample),
    ]:
        assert json.loads((ROOT / path).read_text()) == model.model_json_schema()


def test_file_cannot_set_approval_or_disable_source_rules(bundle):
    data = bundle.model_dump()
    data["document"]["is_approved"] = True
    with pytest.raises(ValidationError):
        PolicyBundle.model_validate(data)
    rules = load_assistant_rules().model_dump()
    rules["source_requirements"]["role_filtered"] = False
    with pytest.raises(ValidationError):
        AssistantRules.model_validate(rules)


@pytest.mark.parametrize("damage", ["duplicate_key", "missing_translation", "unknown_role"])
def test_invalid_file_sections_are_rejected(bundle, damage):
    data = bundle.model_dump()
    if damage == "duplicate_key":
        data["sections"].append(data["sections"][0].copy())
    elif damage == "missing_translation":
        data["sections"][0]["translations"] = {}
    else:
        data["sections"][0]["access_level"] = "superuser"
    with pytest.raises(ValidationError):
        PolicyBundle.model_validate(data)


@pytest.mark.parametrize("role", [UserRole.EMPLOYEE, UserRole.MANAGER])
def test_import_checks_hr_role(db_session, bundle, role):
    actor = db_session.query(User).filter_by(role=role).first()
    before = db_session.query(KnowledgeDocument).count()
    with pytest.raises(HTTPException) as error:
        import_bundle(db_session, bundle, actor)
    assert error.value.status_code == 403
    assert db_session.query(KnowledgeDocument).count() == before


def test_import_is_draft_atomic_and_repeatable(db_session, bundle, monkeypatch):
    from app.services.audit_service import audit_service

    actor = db_session.query(User).filter_by(role=UserRole.HR_ADMIN).first()
    count = db_session.query(KnowledgeDocument).count()
    real_log = audit_service.log_event

    def fail(*args, **kwargs):
        raise RuntimeError("injected audit failure")

    monkeypatch.setattr(audit_service, "log_event", fail)
    with pytest.raises(RuntimeError):
        import_bundle(db_session, bundle, actor)
    assert db_session.query(KnowledgeDocument).count() == count
    monkeypatch.setattr(audit_service, "log_event", real_log)
    result = import_bundle(db_session, bundle, actor)
    document = db_session.get(KnowledgeDocument, result["document_id"])
    assert result["created"] is True and document.is_approved is False
    assert (
        document.chunks[0].translations["kk"]["content"]
        == bundle.sections[0].translations["kk"].content
    )
    assert import_bundle(db_session, bundle, actor) == {
        "document_id": document.id,
        "created": False,
    }
    assert db_session.query(KnowledgeDocument).count() == count + 1
    changed = bundle.model_copy(deep=True)
    changed.sections[0].content += " Changed source."
    with pytest.raises(ValueError, match="already exists"):
        import_bundle(db_session, changed, actor)


def test_template_requires_filling_before_import(db_session):
    template = read_bundle(ROOT / "knowledge/templates/policy.ru-kk.template.json")
    actor = db_session.query(User).filter_by(role=UserRole.HR_ADMIN).first()
    with pytest.raises(ValueError, match="template"):
        import_bundle(db_session, template, actor)
    template.kind = "document"
    with pytest.raises(ValueError, match="placeholders"):
        import_bundle(db_session, template, actor)


def test_import_review_and_ml_citations_preserve_authorization(
    client, db_session, employee_headers, hr_admin_headers, bundle, accepting_model, monkeypatch
):
    actor = db_session.query(User).filter_by(role=UserRole.HR_ADMIN).first()
    bundle.sections[0].access_level = "hr_admin"
    imported = import_bundle(db_session, bundle, actor)
    document = db_session.get(KnowledgeDocument, imported["document_id"])
    chunk_id = document.chunks[0].id
    path = f"/api/v1/ai/sources/{chunk_id}?language=ru"
    assert client.get(path, headers=hr_admin_headers).status_code == 404
    approved = client.patch(
        f"/api/v1/admin/knowledge/documents/{document.id}",
        headers=hr_admin_headers,
        json={"is_approved": True, "expected_revision": document.revision},
    )
    assert approved.status_code == 200
    monkeypatch.setattr(settings, "AI_RETRIEVAL_MODE", "ml")
    monkeypatch.setattr(settings, "AI_RETRIEVAL_MODEL_PATH", str(accepting_model))
    for headers, authorized in [(employee_headers, False), (hr_admin_headers, True)]:
        headers = {**headers, "Accept-Language": "ru"}
        answer = client.post(
            "/api/v1/ai/chat", headers=headers, json={"question": "Как подать заявку на отпуск?"}
        ).json()
        citations = {source["chunk_id"] for source in answer["sources"]}
        assert (chunk_id in citations) is authorized
        response = client.get(path, headers=headers)
        assert response.status_code == (200 if authorized else 404)
        if authorized:
            assert response.json()["content"] == bundle.sections[0].content
            assert bundle.sections[0].content in answer["answer"]
    client.patch(
        f"/api/v1/admin/knowledge/documents/{document.id}",
        headers=hr_admin_headers,
        json={"is_active": False},
    )
    assert client.get(path, headers=hr_admin_headers).status_code == 404


def test_broken_ml_model_keeps_existing_safe_retrieval(
    client, employee_headers, monkeypatch, tmp_path, caplog
):
    monkeypatch.setattr(settings, "AI_RETRIEVAL_MODE", "ml")
    monkeypatch.setattr(settings, "AI_RETRIEVAL_MODEL_PATH", str(tmp_path / "absent.json"))
    answer = client.post(
        "/api/v1/ai/chat", headers=employee_headers, json={"question": "How to request vacation?"}
    ).json()
    assert answer["answer_status"] == "grounded"
    assert "using lexical retrieval" in caplog.text
    assert "How to request vacation" not in caplog.text
    assert str(tmp_path) not in caplog.text


@pytest.mark.parametrize("damage", ["nan", "extra_field", "unknown_features"])
def test_model_artifacts_reject_unsafe_formats(accepting_model, damage):
    data = json.loads(accepting_model.read_text())
    if damage == "nan":
        data["coefficients"][0] = float("nan")
    elif damage == "extra_field":
        data["execute"] = "arbitrary code"
    else:
        data["feature_names"][0] = "unknown"
    accepting_model.write_text(json.dumps(data))
    with pytest.raises(ValidationError):
        load_relevance_model(accepting_model)


def test_offline_predictions_respect_language_privacy_and_scope(accepting_model):
    model = load_relevance_model(accepting_model)
    corpus = load_corpus()
    private = RetrievalQuery(question="Покажи зарплату коллеги", language="ru", role="employee")
    assert predict(private, corpus, model) == {"status": "unauthorized", "sources": []}
    question = RetrievalQuery(
        question="Как подать заявку на отпуск?", language="kk", role="employee"
    )
    assert all(
        source["language"] == "kk" for source, score in predict(question, corpus, model)["sources"]
    )
    restricted = [source for source in corpus if source["access_level"] != "all"]
    assert predict(question, restricted, model)["sources"] == []


def test_dataset_rejects_cross_split_group_leakage(tmp_path):
    for name in ("train", "validation", "test"):
        text = (ROOT / "ml/data" / (name + ".jsonl")).read_text()
        (tmp_path / (name + ".jsonl")).write_text(text)
    path = tmp_path / "validation.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    rows[0]["group_id"] = "vacation-1"
    path.write_text("\n".join(json.dumps(row) for row in rows))
    with pytest.raises(ValueError, match="leaks"):
        validate_splits(tmp_path, load_corpus())


def test_training_and_portable_artifact_run_end_to_end(
    tmp_path, client, employee_headers, monkeypatch
):
    pytest.importorskip("sklearn")
    from ml.train import train

    output, report = tmp_path / "model.json", tmp_path / "report.json"
    model = train(ROOT / "ml/data", output, report)
    assert load_relevance_model(output) == model
    result = json.loads(report.read_text())
    assert result["training_pairs"] > 100
    assert result["split_sizes"]["test"] == 22
    assert result["synthetic_only"] is True
    assert result["test"]["counts"]["examples"] == 22
    assert result["test"]["privacy_refusal_rate"] == 1.0
    query = RetrievalQuery(question="Как подать заявку на отпуск?", language="ru", role="employee")
    prediction = predict(query, load_corpus(), model)
    assert prediction["status"] == "grounded"
    assert prediction["sources"][0][0]["source_id"] == "demo-vacation:guide"
    monkeypatch.setattr(settings, "AI_RETRIEVAL_MODE", "ml")
    monkeypatch.setattr(settings, "AI_RETRIEVAL_MODEL_PATH", str(output))
    response = client.post(
        "/api/v1/ai/chat",
        headers={**employee_headers, "Accept-Language": "ru"},
        json={"question": query.question},
    )
    assert response.status_code == 200
    answer = response.json()
    assert answer["answer_status"] == "grounded"
    citation = answer["sources"][0]
    source = client.get(
        f"/api/v1/ai/sources/{citation['chunk_id']}?revision={citation['document_revision']}&language=ru",
        headers=employee_headers,
    ).json()
    assert source["content"] in answer["answer"]


def test_policy_dates_import_and_legacy_bundle_fingerprint(db_session, bundle):
    import hashlib
    from datetime import date

    original = bundle.model_dump(mode="json")
    for field in ("policy_key", "priority", "effective_from", "effective_until", "known_conflict"):
        del original["document"][field]
    previous_hash = hashlib.sha256(
        json.dumps(original, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()
    assert bundle.fingerprint() == previous_hash
    bundle.document.effective_from = date(2026, 10, 1)
    assert bundle.fingerprint() != previous_hash
    actor = db_session.query(User).filter_by(role=UserRole.HR_ADMIN).first()
    result = import_bundle(db_session, bundle, actor)
    assert result["created"]
    assert import_bundle(db_session, bundle, actor) == {
        "document_id": result["document_id"],
        "created": False,
    }
    assert db_session.get(KnowledgeDocument, result["document_id"]).effective_from == date(
        2026, 10, 1
    )
