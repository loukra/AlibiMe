import XCTest
@testable import BelievableCall

@MainActor
final class AppModelTests: XCTestCase {
    private func makeApp(store: SessionStoring) -> AppModel {
        // Inject a stub transport so this suite emits zero real network — even
        // the fire-and-forget device registration on signIn hits the stub.
        let env = AppEnvironment(baseURL: URL(string: "http://localhost")!,
                                 transport: StubTransport(),
                                 sessionStore: store,
                                 prefs: InMemoryPreferences())
        return AppModel(env: env)
    }

    func testRestoreWithStoredSessionAuthenticates() {
        let stored = Session(token: "tok-restored", userID: "u1", maskedNumber: "+14******123")
        let app = makeApp(store: InMemorySessionStore(session: stored))
        XCTAssertEqual(app.phase, .launching)
        app.restore()
        XCTAssertEqual(app.phase, .authenticated)
        XCTAssertEqual(app.session?.token, "tok-restored")
        XCTAssertEqual(app.env.tokenHolder.sessionToken, "tok-restored")
    }

    func testRestoreWithoutSessionIsUnauthenticated() {
        let app = makeApp(store: InMemorySessionStore())
        app.restore()
        XCTAssertEqual(app.phase, .unauthenticated)
        XCTAssertNil(app.env.tokenHolder.sessionToken)
    }

    func testSignInPersistsAndSetsToken() {
        let store = InMemorySessionStore()
        let app = makeApp(store: store)
        app.signIn(Session(token: "new-tok", userID: "u2", maskedNumber: nil))
        XCTAssertEqual(app.phase, .authenticated)
        XCTAssertEqual(store.load()?.token, "new-tok")
        XCTAssertEqual(app.env.tokenHolder.sessionToken, "new-tok")
        XCTAssertFalse(app.sessionExpiredNotice)
    }

    func testSignOutClearsEverything() {
        let store = InMemorySessionStore(session: Session(token: "t", userID: "u", maskedNumber: nil))
        let app = makeApp(store: store)
        app.restore()
        app.signOut()
        XCTAssertEqual(app.phase, .unauthenticated)
        XCTAssertNil(store.load())
        XCTAssertNil(app.env.tokenHolder.sessionToken)
    }

    func testSessionExpirySetsNoticeAndClears() {
        let store = InMemorySessionStore(session: Session(token: "t", userID: "u", maskedNumber: nil))
        let app = makeApp(store: store)
        app.restore()
        app.handleSessionExpired()
        XCTAssertEqual(app.phase, .unauthenticated)
        XCTAssertTrue(app.sessionExpiredNotice)
        XCTAssertNil(store.load())
    }

    func testFactoriesWireSessionExpiryToRootModel() async {
        let app = makeApp(store: InMemorySessionStore())
        let home = app.makeHomeViewModel()
        // Driving an expiry through the home VM should flip the app to unauth.
        home.onSessionExpired?()
        XCTAssertEqual(app.phase, .unauthenticated)
        XCTAssertTrue(app.sessionExpiredNotice)
    }
}
