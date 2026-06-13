import XCTest
@testable import BelievableCall

@MainActor
final class HomeViewModelTests: XCTestCase {
    private func makeVM(templates: [TemplateSummary] = Fixtures.templates,
                        profile: UserProfile = Fixtures.profile(),
                        request: MockRequestService = MockRequestService(),
                        prefs: PreferencesStoring = InMemoryPreferences()) -> HomeViewModel {
        HomeViewModel(templateService: MockTemplateService(templates: templates),
                      requestService: request,
                      profileService: MockProfileService(profile: profile),
                      prefs: prefs)
    }

    func testLoadPopulatesAndSelectsFirstTemplate() async {
        let vm = makeVM()
        await vm.load()
        XCTAssertFalse(vm.templates.isEmpty)
        XCTAssertNotNil(vm.selectedTemplate)
        XCTAssertEqual(vm.creditsAvailable, 3)
        XCTAssertEqual(vm.maskedNumber, "+14******123")
    }

    func testLoadRestoresSavedTemplateSelection() async {
        let prefs = InMemoryPreferences()
        prefs.selectedTemplateID = "tpl-safety"
        let vm = makeVM(prefs: prefs)
        await vm.load()
        XCTAssertEqual(vm.selectedTemplate?.id, "tpl-safety")
    }

    func testChannelFilteringForTextOnlyTemplate() async {
        // tpl-roommate supports only .text in fixtures.
        let prefs = InMemoryPreferences()
        prefs.selectedTemplateID = "tpl-roommate"
        let vm = makeVM(prefs: prefs)
        await vm.load()
        XCTAssertEqual(vm.availableChannels, [.text])
        // Even though default channel is .call, reconcile forces .text.
        XCTAssertEqual(vm.channel, .text)
    }

    func testChannelFilteringForCallOnlyTemplate() async {
        let prefs = InMemoryPreferences()
        prefs.selectedTemplateID = "tpl-boss-travel" // call only
        let vm = makeVM(prefs: prefs)
        await vm.load()
        XCTAssertEqual(vm.availableChannels, [.call])
        XCTAssertEqual(vm.channel, .call)
    }

    func testSelectingUnsupportedChannelIsIgnored() async {
        let prefs = InMemoryPreferences()
        prefs.selectedTemplateID = "tpl-roommate" // text only
        let vm = makeVM(prefs: prefs)
        await vm.load()
        vm.selectChannel(.call)
        XCTAssertEqual(vm.channel, .text) // unchanged
    }

    func testSwitchingTemplateReconcilesChannel() async {
        let vm = makeVM()
        await vm.load()
        vm.selectChannel(.text)
        // Switch to a call-only template; channel should fall back to .call.
        let callOnly = vm.templates.first { $0.id == "tpl-boss-travel" }!
        vm.selectTemplate(callOnly)
        XCTAssertEqual(vm.channel, .call)
    }

    func testTimingPresetSelectionPersists() async {
        let prefs = InMemoryPreferences()
        let vm = makeVM(prefs: prefs)
        await vm.load()
        vm.selectTiming(.in5Minutes)
        XCTAssertEqual(vm.timing, .in5Minutes)
        XCTAssertEqual(prefs.lastTimingDelay, 300)
    }

    func testPrimaryCTATitleAdaptsToChannelAndTiming() async {
        let vm = makeVM()
        await vm.load()
        vm.selectChannel(.call)
        vm.selectTiming(.now)
        XCTAssertEqual(vm.primaryCTATitle, "Call me now")
        vm.selectChannel(.text)
        vm.selectTiming(.in30Seconds)
        XCTAssertEqual(vm.primaryCTATitle, "Text me in 30 seconds")
        vm.selectTiming(.schedule(Date().addingTimeInterval(600)))
        XCTAssertEqual(vm.primaryCTATitle, "Schedule text")
    }

    func testSendBuildsDraftAndSetsActiveRequest() async {
        let request = MockRequestService(created: Fixtures.scheduledRequest(channel: .call, seconds: 30))
        let vm = makeVM(request: request)
        await vm.load()
        vm.selectChannel(.call)
        vm.selectTiming(.in30Seconds)
        await vm.send()
        XCTAssertEqual(request.lastDraft?.channel, .call)
        XCTAssertEqual(request.lastDraft?.timing, .in30Seconds)
        XCTAssertEqual(request.lastDraft?.templateID, vm.selectedTemplate?.id)
        XCTAssertTrue(vm.hasActiveRequest)
    }

    func testCannotSendWithoutCredits() async {
        let vm = makeVM(profile: Fixtures.profile(credits: 0))
        await vm.load()
        XCTAssertFalse(vm.canSend)
    }

    func testActiveRequestBlocksSecondSend() async {
        let active = Fixtures.scheduledRequest()
        let vm = makeVM(profile: Fixtures.profile(activeRequest: active))
        await vm.load()
        XCTAssertTrue(vm.hasActiveRequest)
        XCTAssertFalse(vm.canSend)
    }

    func testInsufficientCreditsErrorMapsToCopy() async {
        let request = MockRequestService()
        request.createError = APIError.api(code: "insufficient_credits", message: "x", retryable: false, requestID: nil)
        let vm = makeVM(request: request)
        await vm.load()
        await vm.send()
        XCTAssertEqual(vm.errorMessage, "You’re out of credits. Add more to keep sending.")
    }

    func testSessionExpiryRoutesToCallback() async {
        let request = MockRequestService()
        request.createError = APIError.sessionExpired
        let vm = makeVM(request: request)
        var expired = false
        vm.onSessionExpired = { expired = true }
        await vm.load()
        await vm.send()
        XCTAssertTrue(expired)
        XCTAssertNil(vm.errorMessage) // routed, not shown inline
    }

    func testCancelActiveClearsRequest() async {
        let active = Fixtures.scheduledRequest()
        let vm = makeVM(profile: Fixtures.profile(activeRequest: active))
        await vm.load()
        await vm.cancelActive()
        XCTAssertNil(vm.activeRequest)
    }

    func testRefreshActiveRequestClearsWhenTerminal() async {
        let active = Fixtures.scheduledRequest()
        let request = MockRequestService(created: active)
        request.created = RequestSummary(id: active.id, channel: .call, status: .completed,
                                         scheduledKind: nil, executeAt: active.executeAt,
                                         requestedAt: nil, cancelable: false, lastErrorCode: nil)
        let vm = makeVM(profile: Fixtures.profile(activeRequest: active), request: request)
        await vm.load()
        await vm.refreshActiveRequest()
        XCTAssertNil(vm.activeRequest) // terminal -> cleared
    }

    func testTemplatesGroupedByCategoryInOrder() async {
        let vm = makeVM()
        await vm.load()
        let order = vm.templatesByCategory.map(\.category)
        XCTAssertEqual(order.first, .work)         // work sorts first
        XCTAssertEqual(order.last, .safety)        // safety sorts last
    }
}
