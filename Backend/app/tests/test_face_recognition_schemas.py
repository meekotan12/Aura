from app.schemas.face_recognition import FaceRegistrationResponse


def test_face_registration_response_allows_missing_student_id() -> None:
    response = FaceRegistrationResponse(
        message="Face registered successfully.",
        student_id=None,
        liveness={"label": "Bypassed", "score": 1.0},
    )

    assert response.student_id is None
