import XCTest
@testable import BelievableCall

/// End-to-end tests that drive the real backend through the app's own
/// networking + service layer. They are skipped unless `BC_BACKEND_URL` points
/// at a running server (started with mock providers), so `swift test` is green
/// out of the box and these run on demand. See frontend/README.md.
///
/// With mock providers the OTP code is always `123456`.
final class BackendIntegrationTests: XCTestCase {
    private var baseURL: URL!
    private let mockOTP = "123456"

    override func setUpWithError() throws {
        guard let raw = ProcessInfo.processInfo.environment["BC_BACKEND_URL"],
              let url = URL(string: raw) else {
            throw XCTSkip("Set BC_BACKEND_URL to run backend integration tests.")
        }
        baseURL = url
    }

    // MARK: Helpers

    private func makeEnvironment() -> AppEnvironment {
        AppEnvironment(baseURL: baseURL,
                       sessionStore: InMemorySessionStore(),
                       prefs: InMemoryPreferences())
    }

    /// Unique-ish US number in the reserved 555-01xx test range, which
    /// libphonenumber treats as valid (and the mock OTP accepts).
    private func freshPhoneNumber() -> String {
        let suffix = String(format: "%02d", Int.random(in: 0...99))
        return "+141555501" + suffix // +1 415 555 01XX
    }

    /// Runs the full OTP login and returns an authenticated environment + token.
    @discardableResult
    private func authenticate(_ env: AppEnvironment, phone: String) async throws -> Session {
        let start = try await env.auth.start(phoneNumber: phone, locale: "en", deviceID: env.prefs.deviceID)
        XCTAssertFalse(start.verificationID.isEmpty)
        let session = try await env.auth.confirm(verificationID: start.verificationID,
                                                 code: mockOTP, deviceID: env.prefs.deviceID)
        env.tokenHolder.update(session.token)
        return session
    }

    /// Cancels any pre-existing active request so a test can create a fresh one.
    private func clearActiveRequest(_ env: AppEnvironment) async throws {
        let me = try await env.profile.me()
        if let active = me.activeRequest, active.status.isLive {
            _ = try? await env.requests.cancel(id: active.id)
        }
    }

    // MARK: Tests

    func testFullLoginFlow() async throws {
        let env = makeEnvironment()
        let session = try await authenticate(env, phone: freshPhoneNumber())
        XCTAssertFalse(session.token.isEmpty)
        XCTAssertNotNil(session.maskedNumber)
        // Masked number must not reveal the full number.
        XCTAssertTrue(session.maskedNumber?.contains("*") ?? false)
    }

    func testWrongOTPIsRejected() async throws {
        let env = makeEnvironment()
        let start = try await env.auth.start(phoneNumber: freshPhoneNumber(), locale: "en", deviceID: "d")
        do {
            _ = try await env.auth.confirm(verificationID: start.verificationID, code: "000000", deviceID: "d")
            XCTFail("expected wrong-code rejection")
        } catch let error as APIError {
            XCTAssertNotNil(ErrorCopy.userMessage(for: error))
        }
    }

    func testMeReportsVerifiedNumberAndCredits() async throws {
        let env = makeEnvironment()
        try await authenticate(env, phone: freshPhoneNumber())
        let profile = try await env.profile.me()
        XCTAssertTrue(profile.phone.isVerified)
        XCTAssertGreaterThanOrEqual(profile.entitlements.creditsAvailable, 1)
    }

    func testTemplatesCatalogLoadsAndMaps() async throws {
        let env = makeEnvironment()
        try await authenticate(env, phone: freshPhoneNumber())
        let templates = try await env.templates.list()
        XCTAssertFalse(templates.isEmpty)
        // At least one template should support each channel structure.
        XCTAssertTrue(templates.contains { $0.supports(.call) })
        // Categories map to the known enum (no crashes / unknowns leak).
        XCTAssertTrue(templates.allSatisfy { TemplateCategory.allCases.contains($0.category) })
    }

    func testCreateGetCancelCallRequest() async throws {
        let env = makeEnvironment()
        try await authenticate(env, phone: freshPhoneNumber())
        try await clearActiveRequest(env)
        let templates = try await env.templates.list()
        let callTemplate = try XCTUnwrap(templates.first { $0.supports(.call) })

        let draft = RequestDraft(templateID: callTemplate.id, channel: .call, timing: .in30Seconds)
        let created = try await env.requests.create(draft)
        XCTAssertEqual(created.status, .scheduled)
        XCTAssertTrue(created.cancelable)

        let fetched = try await env.requests.get(id: created.id)
        XCTAssertEqual(fetched.id, created.id)
        XCTAssertEqual(fetched.channel, .call)

        let canceled = try await env.requests.cancel(id: created.id)
        XCTAssertEqual(canceled.status, .canceled)
    }

    func testCreateTextRequestWhenSupported() async throws {
        let env = makeEnvironment()
        try await authenticate(env, phone: freshPhoneNumber())
        try await clearActiveRequest(env)
        let templates = try await env.templates.list()
        guard let smsTemplate = templates.first(where: { $0.supports(.text) }) else {
            throw XCTSkip("Backend has no SMS-capable template.")
        }
        let created = try await env.requests.create(
            RequestDraft(templateID: smsTemplate.id, channel: .text, timing: .now)
        )
        XCTAssertEqual(created.channel, .text)
        _ = try? await env.requests.cancel(id: created.id)
    }

    func testActiveRequestBlocksSecond() async throws {
        let env = makeEnvironment()
        try await authenticate(env, phone: freshPhoneNumber())
        try await clearActiveRequest(env)
        let templates = try await env.templates.list()
        let template = try XCTUnwrap(templates.first { $0.supports(.call) })

        let first = try await env.requests.create(
            RequestDraft(templateID: template.id, channel: .call, timing: .in5Minutes)
        )
        defer { Task { _ = try? await env.requests.cancel(id: first.id) } }

        do {
            _ = try await env.requests.create(
                RequestDraft(templateID: template.id, channel: .call, timing: .in5Minutes)
            )
            XCTFail("expected active_request_exists")
        } catch let error as APIError {
            XCTAssertEqual(error.backendCode, "active_request_exists")
        }
    }

    func testScheduleWindowRejectsBeyond24h() async throws {
        let env = makeEnvironment()
        try await authenticate(env, phone: freshPhoneNumber())
        try await clearActiveRequest(env)
        let templates = try await env.templates.list()
        let template = try XCTUnwrap(templates.first { $0.supports(.call) })
        let tooFar = Date().addingTimeInterval(48 * 3600)
        do {
            _ = try await env.requests.create(
                RequestDraft(templateID: template.id, channel: .call, timing: .schedule(tooFar))
            )
            XCTFail("expected invalid_schedule_window")
        } catch let error as APIError {
            XCTAssertEqual(error.backendCode, "invalid_schedule_window")
        }
    }

    func testHistoryReflectsCanceledRequest() async throws {
        let env = makeEnvironment()
        try await authenticate(env, phone: freshPhoneNumber())
        try await clearActiveRequest(env)
        let templates = try await env.templates.list()
        let template = try XCTUnwrap(templates.first { $0.supports(.call) })
        let created = try await env.requests.create(
            RequestDraft(templateID: template.id, channel: .call, timing: .in30Seconds)
        )
        _ = try await env.requests.cancel(id: created.id)

        let page = try await env.history.list(limit: 20, offset: 0)
        XCTAssertTrue(page.items.contains { $0.id == created.id })
    }

    func testUnauthorizedWithoutToken() async throws {
        let env = makeEnvironment() // no token set
        do {
            _ = try await env.profile.me()
            XCTFail("expected unauthorized")
        } catch let error as APIError {
            XCTAssertTrue(error.requiresReauth)
        }
    }

    func testEntitlementsEndpoint() async throws {
        let env = makeEnvironment()
        try await authenticate(env, phone: freshPhoneNumber())
        let me = try await env.profile.me()
        XCTAssertGreaterThanOrEqual(me.entitlements.creditsAvailable, 0)
    }

    func testDeviceRegistration() async throws {
        let env = makeEnvironment()
        try await authenticate(env, phone: freshPhoneNumber())
        try await env.devices.register(deviceID: env.prefs.deviceID, pushToken: "test-token",
                                       appVersion: "1.0", osVersion: "17.0")
        // No throw == success; the endpoint returns the device record.
    }
}
