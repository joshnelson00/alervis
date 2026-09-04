from halo.operations import (
    ALL_ASSESSMENT_GRADES,
    FORUM_COUNT_FILTERS,
    GET_ALL_CLASSES,
    GRADE_OVERVIEW,
    REGISTRY,
    SIDEBAR_FORUM_NOTIFICATIONS,
    SIDEBAR_GRADEBOOK_NOTIFICATIONS,
    UPCOMING_ASSIGNMENTS,
)


def test_registry_is_keyed_by_operation_name():
    for name, op in REGISTRY.items():
        assert name == op.name


def test_query_declares_its_own_operation_name():
    # operationName and Gql-Operation-Name must agree with the query text.
    for op in REGISTRY.values():
        assert op.name in op.query


def test_course_context_flags_match_reference_docs():
    # UpcomingAssignments is the only documented operation needing both headers.
    assert UPCOMING_ASSIGNMENTS.needs_slug_header
    assert UPCOMING_ASSIGNMENTS.needs_course_class_header

    for op in (ALL_ASSESSMENT_GRADES, GRADE_OVERVIEW, SIDEBAR_GRADEBOOK_NOTIFICATIONS):
        assert op.needs_slug_header
        assert not op.needs_course_class_header

    # Forum notifications carry course context in classId, not a header.
    assert not SIDEBAR_FORUM_NOTIFICATIONS.needs_slug_header
    assert not SIDEBAR_FORUM_NOTIFICATIONS.needs_course_class_header

    assert not GET_ALL_CLASSES.needs_slug_header
    assert not GET_ALL_CLASSES.needs_course_class_header


def test_get_all_classes_takes_no_variables():
    assert "(" not in GET_ALL_CLASSES.query.splitlines()[0]


def test_forum_filter_uses_filter_side_names():
    # The filter names differ from the keys the API returns (CQ, GROUP).
    sent = {f["forumType"] for f in FORUM_COUNT_FILTERS["forumFilters"]}
    assert "CLASS_QUESTIONS" in sent
    assert "TEAM_FORUM" in sent
    assert FORUM_COUNT_FILTERS["fetchOnlyCounts"] is True
