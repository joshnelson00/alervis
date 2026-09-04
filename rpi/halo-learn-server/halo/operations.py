"""The documented read-only Halo GraphQL operations.

Query text and course-context requirements come from the halo-api-reference
docs. Each operation page is authoritative for its own header block; the flags
here mirror those pages.
"""

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class Operation:
    name: str
    query: str
    # Whether this operation sends Current-Class-Slug-Id / Current-Course-Class-Id.
    needs_slug_header: bool = False
    needs_course_class_header: bool = False


GET_ALL_CLASSES = Operation(
    name="GetAllClasses",
    query="""query GetAllClasses {
  getAllClasses {
    classDetails {
      classCode
      className
      courseClassId
      courseClassStage
      courseClassStatus
      courseClassUserStatus
      endDate
      sequence
      slugId
      startDate
      unitTitle
    }
    role
  }
}""",
)

UPCOMING_ASSIGNMENTS = Operation(
    name="UpcomingAssignments",
    query="""query UpcomingAssignments($slugId: String!) {
  currentClass: getCourseClassBySlugId(slugId: $slugId) {
    id
    units {
      id
      assessments {
        id
        title
        dueDate
        startDate
        type
        points
        description
        requiresLopesWrite
        rubric { id }
        attachments { id resourceId title }
      }
    }
  }
}""",
    needs_slug_header=True,
    needs_course_class_header=True,
)

ALL_ASSESSMENT_GRADES = Operation(
    name="AllAssessmentGrades",
    query="""query AllAssessmentGrades($courseClassSlugId: String!, $courseUnitId: String) {
  assessmentGrades: getAllClassGrades(
    courseClassSlugId: $courseClassSlugId
    courseUnitId: $courseUnitId
  ) {
    grades {
      id
      status
      dueDate
      accommodatedDueDate
      userLastSeenDate
      isEverReassigned
      user { id }
      assessment { id inPerson }
      assignmentSubmission { submissionDate }
      userQuizAssessment { userQuizId accommodatedDuration }
    }
  }
}""",
    needs_slug_header=True,
)

GRADE_OVERVIEW = Operation(
    name="GradeOverview",
    query="""query GradeOverview($courseClassSlugId: String!, $courseClassUserIds: [String]) {
  gradeOverview: getAllClassGrades(
    courseClassSlugId: $courseClassSlugId
    courseClassUserIds: $courseClassUserIds
  ) {
    finalGrade {
      id
      finalPoints
      gradeValue
      isPublished
      maxPoints
    }
    grades {
      id
      status
      dueDate
      accommodatedDueDate
      finalPoints
      assessment { id }
      assignmentSubmission { id submissionDate }
    }
  }
}""",
    needs_slug_header=True,
)

SIDEBAR_GRADEBOOK_NOTIFICATIONS = Operation(
    name="SidebarGradebookNotifications",
    query="""query SidebarGradebookNotifications($slugId: String!) {
  gradebook: getGradingNotifications(slugId: $slugId) {
    count
  }
}""",
    needs_slug_header=True,
)

SIDEBAR_FORUM_NOTIFICATIONS = Operation(
    name="SidebarForumNotifications",
    query="""query SidebarForumNotifications($classId: String!, $filters: FilterInputGQL) {
  classes: getForumNotifications(classId: $classId, filter: $filters) {
    forumTypes {
      DQ { classes { count } }
      IDQ { classes { count } }
      CQ { classes { count } }
      GROUP { classes { count } }
      ANNOUNCEMENTS { classes { count } }
    }
  }
}""",
)

REGISTRY: Dict[str, Operation] = {
    op.name: op
    for op in (
        GET_ALL_CLASSES,
        UPCOMING_ASSIGNMENTS,
        ALL_ASSESSMENT_GRADES,
        GRADE_OVERVIEW,
        SIDEBAR_GRADEBOOK_NOTIFICATIONS,
        SIDEBAR_FORUM_NOTIFICATIONS,
    )
}

# Default filter for SidebarForumNotifications. The API keys it returns (CQ,
# GROUP) differ from the filter names sent here (CLASS_QUESTIONS, TEAM_FORUM).
FORUM_COUNT_FILTERS = {
    "fetchOnlyCounts": True,
    "forumFilters": [
        {"forumType": "DQ"},
        {"forumType": "IDQ"},
        {"forumType": "CLASS_QUESTIONS"},
        {"forumType": "TEAM_FORUM"},
        {"forumType": "ANNOUNCEMENT"},
    ],
}
