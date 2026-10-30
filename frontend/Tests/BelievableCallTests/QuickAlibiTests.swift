import XCTest
@testable import BelievableCall

final class QuickAlibiTests: XCTestCase {
    private func runner(session: Session? = Session(token: "tok", userID: "u1", maskedNumber: nil),
                        prefs: InMemoryPreferences = InMemoryPreferences(),
                        requests: MockRequestService = MockRequestService()) -> QuickAlibiRunner {
        let store = InMemorySessionStore()
        if let session { store.save(session) }
        return QuickAlibiRunner(sessionStore: store, tokenHolder: TokenHolder(),
                                prefs: prefs, requests: requests)
    }

    func testSendsTheSavedAlibi() async throws {
        let prefs = InMemoryPreferences()
        prefs.quickAlibi = QuickAlibi(templateID: "t1", templateName: "Boss", channel: .call, delaySeconds: 30)
        let requests = MockRequestService()
        let message = try await runner(prefs: prefs, requests: requests).run()
        XCTAssertEqual(message, "Your call comes in 30 seconds.")
        XCTAssertEqual(requests.lastDraft?.templateID, "t1")
        XCTAssertEqual(requests.lastDraft?.timing, .in30Seconds)
    }

    func testFallsBackToLastUsedFromHome() async throws {
        let prefs = InMemoryPreferences()
        prefs.selectedTemplateID = "t9"
        prefs.lastChannel = Channel.text.rawValue
        prefs.lastTimingDelay = 0
        let message = try await runner(prefs: prefs).run()
        XCTAssertEqual(message, "Texting you now.")
    }

    func testDelayOverride() async throws {
        let prefs = InMemoryPreferences()
        prefs.quickAlibi = QuickAlibi(templateID: "t1", templateName: "Boss", channel: .call, delaySeconds: 0)
        let message = try await runner(prefs: prefs).run(delaySeconds: 300)
        XCTAssertEqual(message, "Your call comes in 5 minutes.")
    }

    func testSignedOut() async {
        do {
            _ = try await runner(session: nil).run()
            XCTFail("expected an error")
        } catch {
            XCTAssertEqual(error as? QuickAlibiError, .signedOut)
        }
    }

    func testNothingPickedYet() async {
        do {
            _ = try await runner().run()
            XCTFail("expected an error")
        } catch {
            XCTAssertEqual(error as? QuickAlibiError, .notSetUp)
        }
    }

    func testBackendErrorBecomesReadableCopy() async {
        let prefs = InMemoryPreferences()
        prefs.quickAlibi = QuickAlibi(templateID: "t1", templateName: "Boss", channel: .call, delaySeconds: 0)
        let requests = MockRequestService()
        requests.createError = APIError.api(code: "insufficient_credits", message: "", retryable: false, requestID: nil)
        do {
            _ = try await runner(prefs: prefs, requests: requests).run()
            XCTFail("expected an error")
        } catch {
            XCTAssertEqual(error as? QuickAlibiError, .failed("You’re out of credits. Add more to keep sending."))
        }
    }

    func testStoredInUserDefaults() {
        let defaults = UserDefaults(suiteName: "quick-alibi-test")!
        defaults.removePersistentDomain(forName: "quick-alibi-test")
        let prefs = UserDefaultsPreferences(defaults: defaults)
        let alibi = QuickAlibi(templateID: "t1", templateName: "Boss", channel: .text, delaySeconds: 300)
        prefs.quickAlibi = alibi
        XCTAssertEqual(UserDefaultsPreferences(defaults: defaults).quickAlibi, alibi)
        prefs.quickAlibi = nil
        XCTAssertNil(prefs.quickAlibi)
    }

    @MainActor
    func testSettingsPicksChannelTheTemplateSupports() async {
        let prefs = InMemoryPreferences()
        let vm = SettingsViewModel(profileService: MockProfileService(), auth: MockAuthService(),
                                   creditPackages: MockCreditPackagesService(),
                                   templates: MockTemplateService(), prefs: prefs)
        await vm.load()
        let textOnly = vm.quickAlibiTemplates.first { $0.supportedChannels == [.text] }!
        vm.setQuickAlibi(templateID: textOnly.id)
        XCTAssertEqual(prefs.quickAlibi?.channel, .text)
        vm.setQuickAlibiDelay(30)
        XCTAssertEqual(prefs.quickAlibi?.delaySeconds, 30)
        vm.setQuickAlibi(templateID: nil)
        XCTAssertNil(prefs.quickAlibi)
    }
}

@MainActor
final class AccountDeletionTests: XCTestCase {
    func testDeleteSignsOutAndClearsLocalPicks() async {
        let profile = MockProfileService()
        let prefs = InMemoryPreferences()
        prefs.quickAlibi = QuickAlibi(templateID: "t1", templateName: "Boss", channel: .call, delaySeconds: 0)
        prefs.selectedTemplateID = "t1"
        let vm = SettingsViewModel(profileService: profile, auth: MockAuthService(),
                                   creditPackages: MockCreditPackagesService(), prefs: prefs)
        var signedOut = false
        vm.onSignOut = { signedOut = true }
        await vm.deleteAccount()
        XCTAssertTrue(profile.deleted)
        XCTAssertTrue(signedOut)
        XCTAssertNil(prefs.quickAlibi)
        XCTAssertNil(prefs.selectedTemplateID)
    }

    func testFailedDeleteStaysSignedIn() async {
        let profile = MockProfileService()
        profile.error = APIError.transport(message: "offline")
        let vm = SettingsViewModel(profileService: profile, auth: MockAuthService(),
                                   creditPackages: MockCreditPackagesService())
        var signedOut = false
        vm.onSignOut = { signedOut = true }
        await vm.deleteAccount()
        XCTAssertFalse(signedOut)
        XCTAssertNotNil(vm.errorMessage)
    }
}
