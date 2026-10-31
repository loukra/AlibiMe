import XCTest
@testable import BelievableCall

final class CodingAndErrorTests: XCTestCase {
    // MARK: Date coding

    func testParsesFractionalAndPlainISO8601() {
        XCTAssertNotNil(BCCoding.parseDate("2026-06-13T14:37:59.855827Z"))
        XCTAssertNotNil(BCCoding.parseDate("2026-06-13T14:37:59Z"))
        XCTAssertNil(BCCoding.parseDate("not-a-date"))
    }

    func testDateEncodeIsRoundTrippable() throws {
        struct Box: Codable, Equatable { let at: Date }
        let original = BCCoding.parseDate("2026-06-13T14:37:59.855Z")!
        let data = try BCCoding.encoder.encode(Box(at: original))
        let decoded = try BCCoding.decoder.decode(Box.self, from: data)
        XCTAssertEqual(decoded.at.timeIntervalSince1970, original.timeIntervalSince1970, accuracy: 0.01)
    }

    func testDecodesCreateResponseWithMicrosecondDate() throws {
        let json = """
        {"request_id":"r1","channel":"call","status":"scheduled",
         "execute_at":"2026-06-13T14:37:59.855827Z","credits_available":3,"cancelable":true}
        """.data(using: .utf8)!
        let dto = try BCCoding.decoder.decode(CreateRequestResponseDTO.self, from: json)
        XCTAssertEqual(dto.request_id, "r1")
        XCTAssertTrue(dto.cancelable)
    }

    // MARK: Error envelope mapping

    func testMapErrorDecodesEnvelope() {
        let body = """
        {"error":{"code":"insufficient_credits","message":"no credits","retryable":false,"request_id":"req-1"}}
        """.data(using: .utf8)!
        let error = APIClient.mapError(status: 402, data: body)
        guard case let .api(code, _, retryable, requestID) = error else {
            return XCTFail("expected .api")
        }
        XCTAssertEqual(code, "insufficient_credits")
        XCTAssertFalse(retryable)
        XCTAssertEqual(requestID, "req-1")
    }

    func testMapErrorRecognizesUnauthorizedAndSessionExpired() {
        let unauth = """
        {"error":{"code":"unauthorized","message":"x","retryable":false,"request_id":null}}
        """.data(using: .utf8)!
        XCTAssertEqual(APIClient.mapError(status: 401, data: unauth), .unauthorized)

        let expired = """
        {"error":{"code":"session_expired","message":"x","retryable":false,"request_id":null}}
        """.data(using: .utf8)!
        XCTAssertEqual(APIClient.mapError(status: 401, data: expired), .sessionExpired)
    }

    func testMapErrorFallsBackOnUnparseableBody() {
        let error = APIClient.mapError(status: 500, data: Data("oops".utf8))
        XCTAssertEqual(error, .unexpectedStatus(500))
    }

    // MARK: Error → user copy

    func testEveryKnownCodeHasCalmCopyWithoutRawCode() {
        let codes = [
            "unauthorized", "session_expired", "phone_not_verified", "invalid_phone_number",
            "unsupported_line_type", "rate_limited", "active_request_exists",
            "template_channel_not_supported", "insufficient_credits", "invalid_schedule_window",
            "request_not_cancelable", "provider_unavailable", "validation_failed", "not_found",
            "invalid_verification_code", "verification_expired",
        ]
        for code in codes {
            let msg = ErrorCopy.userMessage(for: .api(code: code, message: "raw", retryable: false, requestID: nil))
            XCTAssertFalse(msg.isEmpty)
            XCTAssertFalse(msg.contains("_"), "copy for \(code) leaked a raw code: \(msg)")
            XCTAssertFalse(msg.contains(code), "copy for \(code) leaked the code")
        }
    }

    func testWrongSignInCodeSaysSo() {
        // Not the generic "some details weren't accepted".
        let wrong = ErrorCopy.userMessage(for: .api(code: "invalid_verification_code", message: "", retryable: false, requestID: nil))
        let generic = ErrorCopy.userMessage(for: .api(code: "validation_failed", message: "", retryable: false, requestID: nil))
        XCTAssertNotEqual(wrong, generic)
        XCTAssertTrue(wrong.contains("code"))
    }

    func testTransportErrorCopy() {
        let msg = ErrorCopy.userMessage(for: .transport(message: "offline"))
        XCTAssertTrue(msg.contains("connection"))
    }

    func testRequiresReauthFlags() {
        XCTAssertTrue(APIError.unauthorized.requiresReauth)
        XCTAssertTrue(APIError.sessionExpired.requiresReauth)
        XCTAssertTrue(APIError.api(code: "session_expired", message: "", retryable: false, requestID: nil).requiresReauth)
        XCTAssertFalse(APIError.api(code: "insufficient_credits", message: "", retryable: false, requestID: nil).requiresReauth)
        XCTAssertFalse(APIError.transport(message: "x").requiresReauth)
    }
}
