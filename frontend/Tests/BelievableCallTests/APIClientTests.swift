import XCTest
@testable import BelievableCall

/// Captures the outgoing request and returns a canned response.
final class StubTransport: HTTPTransport, @unchecked Sendable {
    var statusCode: Int
    var body: Data
    private(set) var lastRequest: URLRequest?

    init(statusCode: Int = 200, body: Data = Data()) {
        self.statusCode = statusCode
        self.body = body
    }

    func send(_ request: URLRequest) async throws -> (Data, URLResponse) {
        lastRequest = request
        let response = HTTPURLResponse(url: request.url!, statusCode: statusCode,
                                       httpVersion: nil, headerFields: nil)!
        return (body, response)
    }
}

final class TestTokenProvider: TokenProviding, @unchecked Sendable {
    var sessionToken: String?
    init(_ token: String?) { sessionToken = token }
}

final class APIClientTests: XCTestCase {
    func testAttachesBearerTokenAndDecodesSuccess() async throws {
        let stub = StubTransport(statusCode: 200, body: Data("""
        {"templates":[]}
        """.utf8))
        let client = APIClient(baseURL: URL(string: "http://x")!,
                               transport: stub,
                               tokenProvider: TestTokenProvider("secret-token"))
        let service = LiveTemplateService(client: client)
        _ = try await service.list()
        XCTAssertEqual(stub.lastRequest?.value(forHTTPHeaderField: "Authorization"), "Bearer secret-token")
        XCTAssertEqual(stub.lastRequest?.httpMethod, "GET")
        XCTAssertTrue(stub.lastRequest?.url?.absoluteString.hasSuffix("v1/templates") ?? false)
    }

    func testOmitsAuthHeaderForUnauthenticatedEndpoints() async throws {
        let stub = StubTransport(statusCode: 200, body: Data("""
        {"verification_id":"v","channel":"sms","expires_in_seconds":600}
        """.utf8))
        let client = APIClient(baseURL: URL(string: "http://x")!, transport: stub,
                               tokenProvider: TestTokenProvider("tok"))
        let auth = LiveAuthService(client: client)
        _ = try await auth.start(phoneNumber: "+14155550123", locale: "en", deviceID: "d1")
        XCTAssertNil(stub.lastRequest?.value(forHTTPHeaderField: "Authorization"))
        // The phone number went in the body, not as a query/destination param.
        let bodyString = String(data: stub.lastRequest?.httpBody ?? Data(), encoding: .utf8) ?? ""
        XCTAssertTrue(bodyString.contains("+14155550123"))
    }

    func testThrowsMappedAPIErrorOnFailure() async {
        let stub = StubTransport(statusCode: 402, body: Data("""
        {"error":{"code":"insufficient_credits","message":"x","retryable":false,"request_id":"r"}}
        """.utf8))
        let client = APIClient(baseURL: URL(string: "http://x")!, transport: stub,
                               tokenProvider: TestTokenProvider("tok"))
        let service = LiveRequestService(client: client)
        do {
            _ = try await service.create(RequestDraft(templateID: "t", channel: .call, timing: .now))
            XCTFail("expected throw")
        } catch let error as APIError {
            XCTAssertEqual(error.backendCode, "insufficient_credits")
        } catch {
            XCTFail("expected APIError, got \(error)")
        }
    }

    func testCreateRequestSendsPostWith201() async throws {
        let stub = StubTransport(statusCode: 201, body: Data("""
        {"request_id":"r1","channel":"call","status":"scheduled",
         "execute_at":"2026-06-13T14:37:59.855827Z","credits_available":2,"cancelable":true}
        """.utf8))
        let client = APIClient(baseURL: URL(string: "http://x")!, transport: stub,
                               tokenProvider: TestTokenProvider("tok"))
        let service = LiveRequestService(client: client)
        let summary = try await service.create(RequestDraft(templateID: "t", channel: .call, timing: .in30Seconds))
        XCTAssertEqual(summary.id, "r1")
        XCTAssertEqual(summary.status, .scheduled)
        XCTAssertEqual(stub.lastRequest?.httpMethod, "POST")
    }
}
