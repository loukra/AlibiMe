import XCTest
@testable import BelievableCall

@MainActor
final class HomeViewModelTests: XCTestCase {
    private func makeVM(templates: [TemplateSummary] = Fixtures.templates,
                        profile: UserProfile = Fixtures.profile(),
                        profileService: MockProfileService? = nil,
                        request: MockRequestService = MockRequestService(),
                        prefs: PreferencesStoring = InMemoryPreferences(),
                        contacts: ContactsServicing = MockContactsService(),
                        contactLinks: ContactLinkStoring = InMemoryContactLinkStore()) -> HomeViewModel {
        HomeViewModel(templateService: MockTemplateService(templates: templates),
                      requestService: request,
                      profileService: profileService ?? MockProfileService(profile: profile),
                      prefs: prefs,
                      contacts: contacts,
                      contactLinks: contactLinks)
    }

    // MARK: First alibi walkthrough

    private func newUser(credits: Int = 3) -> UserProfile {
        var profile = Fixtures.profile(credits: credits)
        profile.hasRequests = false
        return profile
    }

    func testANewUserIsWalkedThroughTheFirstAlibi() async {
        let vm = makeVM(profile: newUser())
        await vm.load()
        XCTAssertTrue(vm.needsFirstAlibi)
        // One text-capable built-in per category, in category order.
        // The call-only work alibi (tpl-boss-travel) is left out.
        XCTAssertEqual(vm.firstAlibiChoices.map(\.id),
                       ["tpl-boss-urgent", "tpl-sibling", "tpl-friend", "tpl-roommate", "tpl-safety"])
    }

    func testNoWalkthroughForSomeoneWhoSentBeforeSkippedItOrHasNoCredits() async {
        let sent = makeVM(profile: Fixtures.profile())
        await sent.load()
        XCTAssertFalse(sent.needsFirstAlibi, "the account sent something before")

        let prefs = InMemoryPreferences()
        prefs.firstAlibiSeen = true
        let skipped = makeVM(profile: newUser(), prefs: prefs)
        await skipped.load()
        XCTAssertFalse(skipped.needsFirstAlibi, "finished or skipped on this device")

        let broke = makeVM(profile: newUser(credits: 0))
        await broke.load()
        XCTAssertFalse(broke.needsFirstAlibi, "nothing to send it with")
    }

    func testFirstAlibiGoesOutAsATextAtTheChosenTime() async throws {
        let request = MockRequestService()
        let prefs = InMemoryPreferences()
        let vm = makeVM(profile: newUser(), request: request, prefs: prefs)
        await vm.load()
        let choice = try XCTUnwrap(vm.firstAlibiChoices.first)
        let at = Date().addingTimeInterval(3600)

        let sent = await vm.sendFirstAlibi(choice, timing: .schedule(at))
        XCTAssertNotNil(sent)
        XCTAssertEqual(request.lastDraft?.channel, .text)
        XCTAssertEqual(request.lastDraft?.templateID, choice.id)
        XCTAssertEqual(request.lastDraft?.timing, .schedule(at))
        XCTAssertNil(vm.pendingSenderPrompt, "the walkthrough asks about the contact itself")
        XCTAssertTrue(vm.needsFirstAlibi, "still showing until the user is done")

        vm.finishFirstAlibi()
        XCTAssertFalse(vm.needsFirstAlibi)
        XCTAssertTrue(prefs.firstAlibiSeen)
    }

    func testFirstAlibiOffersToSaveTheSenderOnlyOnce() {
        let links = InMemoryContactLinkStore()
        let vm = makeVM(contactLinks: links)
        let sender = Fixtures.senderIdentity()
        XCTAssertTrue(vm.shouldOfferContactSave(for: sender))
        vm.markPromptSkipped(for: sender)
        XCTAssertFalse(vm.shouldOfferContactSave(for: sender))
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

    func testSelectionFollowsTheEditedCopyAndBackAfterReset() async throws {
        let service = MockTemplateService()
        let vm = HomeViewModel(templateService: service, requestService: MockRequestService(),
                               profileService: MockProfileService(profile: Fixtures.profile()),
                               prefs: InMemoryPreferences(), contacts: MockContactsService(),
                               contactLinks: InMemoryContactLinkStore())
        await vm.load()
        let original = try XCTUnwrap(vm.templates.first { $0.id == "tpl-boss-travel" })
        vm.selectTemplate(original)

        var draft = try XCTUnwrap(original.choices)
        draft.displayName = "My boss"
        let copy = try await service.update(id: original.id, draft)
        await vm.refresh()
        XCTAssertEqual(vm.selectedTemplate?.id, copy.id)

        try await service.delete(id: copy.id)
        await vm.refresh()
        XCTAssertEqual(vm.selectedTemplate?.id, original.id)
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

    func testSendCostNoteShowsWhatTheChannelCosts() async {
        var profile = Fixtures.profile()
        profile.creditCosts = CreditCosts(call: 2, text: 1)
        let vm = makeVM(profile: profile)
        await vm.load()
        vm.selectChannel(.call)
        XCTAssertEqual(vm.sendCostNote, "Slide to send · 2 credits")
        vm.selectChannel(.text)
        XCTAssertEqual(vm.sendCostNote, "Slide to send · 1 credit")
    }

    func testSendCostNoteWithoutCostsStillSaysToSlide() async {
        let vm = makeVM()
        await vm.load()
        XCTAssertEqual(vm.sendCostNote, "Slide to send")
    }

    func testSendBuildsDraftAndSyncsNextJobFromBackend() async {
        let created = Fixtures.scheduledRequest(channel: .call, seconds: 30)
        let request = MockRequestService(created: created)
        // After sending, the chip reflects the backend's soonest live job (here,
        // the profile reports one), not the just-created object.
        let vm = makeVM(profile: Fixtures.profile(activeRequest: created), request: request)
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

    func testPendingJobDoesNotBlockSending() async {
        // Multiple jobs may be queued — a pending job no longer disables Send
        // (the backend enforces the cap). The chip is shown alongside the composer.
        let active = Fixtures.scheduledRequest()
        let vm = makeVM(profile: Fixtures.profile(activeRequest: active))
        await vm.load()
        XCTAssertTrue(vm.hasActiveRequest)
        XCTAssertTrue(vm.canSend)
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

    func testCancelActiveShowsNextOrClears() async {
        let active = Fixtures.scheduledRequest()
        let svc = MockProfileService(profile: Fixtures.profile(activeRequest: active))
        let vm = makeVM(profileService: svc)
        await vm.load()
        XCTAssertNotNil(vm.activeRequest)
        // Cancelling the last pending job: the backend then reports none, so the
        // chip clears (had another been pending, it would surface instead).
        svc.profile = Fixtures.profile()
        await vm.cancelActive()
        XCTAssertNil(vm.activeRequest)
    }

    func testRefreshActiveRequestDerivesFromBackend() async {
        let active = Fixtures.scheduledRequest()
        let svc = MockProfileService(profile: Fixtures.profile(activeRequest: active))
        let vm = makeVM(profileService: svc)
        await vm.load()
        XCTAssertNotNil(vm.activeRequest)
        // Job fired/finished -> backend no longer reports a live one.
        svc.profile = Fixtures.profile()
        await vm.refreshActiveRequest()
        XCTAssertNil(vm.activeRequest)
    }

    func testTemplatesGroupedByCategoryInOrder() async {
        let vm = makeVM()
        await vm.load()
        let order = vm.templatesByCategory.map(\.category)
        XCTAssertEqual(order.first, .work)         // work sorts first
        XCTAssertEqual(order.last, .safety)        // safety sorts last
    }

    func testOwnTemplatesAreListedApartFromTheBuiltInOnes() async {
        let own = TemplateSummary(id: "own-1", code: "own", displayName: "My boss",
                                  description: nil, category: .work, callerPersona: "boss",
                                  reasonCode: "custom", isCustom: true, supportedChannels: [.call],
                                  callMaxDurationSeconds: nil, previewOpeningLine: nil,
                                  previewSMSBody: nil)
        let vm = makeVM(templates: Fixtures.templates + [own])
        await vm.load()
        XCTAssertEqual(vm.customTemplates.map(\.id), ["own-1"])
        XCTAssertFalse(vm.templatesByCategory.flatMap(\.templates).contains { $0.isCustom })
    }
}
