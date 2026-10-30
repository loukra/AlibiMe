import XCTest
@testable import BelievableCall

@MainActor
final class SaveContactTests: XCTestCase {
    private func makeVM(request: MockRequestService,
                        contacts: ContactsServicing = MockContactsService(),
                        contactLinks: ContactLinkStoring = InMemoryContactLinkStore())
        -> HomeViewModel {
        HomeViewModel(templateService: MockTemplateService(),
                      requestService: request,
                      profileService: MockProfileService(),
                      prefs: InMemoryPreferences(),
                      contacts: contacts,
                      contactLinks: contactLinks)
    }

    private func smsRequest(binding: String = "b1",
                            recommend: Bool = true,
                            phone: String = "+15551234567") -> RequestSummary {
        RequestSummary(
            id: "r1", channel: .text, status: .scheduled, scheduledKind: nil,
            executeAt: Date().addingTimeInterval(30), requestedAt: nil, cancelable: true,
            lastErrorCode: nil,
            senderIdentity: Fixtures.senderIdentity(bindingID: binding, phone: phone,
                                                    promptRecommended: recommend)
        )
    }

    // MARK: Prompt offering

    func testSmsSuccessOffersContactPrompt() async {
        let vm = makeVM(request: MockRequestService(created: smsRequest()))
        await vm.load()
        vm.selectChannel(.text)
        await vm.send()
        XCTAssertEqual(vm.pendingSenderPrompt?.bindingID, "b1")
    }

    func testCallSuccessOffersContactPrompt() async {
        let callReq = RequestSummary(id: "r1", channel: .call, status: .scheduled,
                                     scheduledKind: nil, executeAt: Date(), requestedAt: nil,
                                     cancelable: true, lastErrorCode: nil,
                                     senderIdentity: Fixtures.senderIdentity(bindingID: "b2"))
        let vm = makeVM(request: MockRequestService(created: callReq))
        await vm.load()
        vm.selectChannel(.call)
        await vm.send()
        XCTAssertEqual(vm.pendingSenderPrompt?.bindingID, "b2")
    }

    func testCallWithoutSenderDoesNotOfferPrompt() async {
        let callReq = RequestSummary(id: "r1", channel: .call, status: .scheduled,
                                     scheduledKind: nil, executeAt: Date(), requestedAt: nil,
                                     cancelable: true, lastErrorCode: nil, senderIdentity: nil)
        let vm = makeVM(request: MockRequestService(created: callReq))
        await vm.load()
        vm.selectChannel(.call)
        await vm.send()
        XCTAssertNil(vm.pendingSenderPrompt)
    }

    func testPromptSuppressedWhenBackendDoesNotRecommend() async {
        let vm = makeVM(request: MockRequestService(created: smsRequest(recommend: false)))
        await vm.load()
        vm.selectChannel(.text)
        await vm.send()
        XCTAssertNil(vm.pendingSenderPrompt)
    }

    func testPromptSuppressedWhenNoSenderNumber() async {
        let vm = makeVM(request: MockRequestService(created: smsRequest(phone: "")))
        await vm.load()
        vm.selectChannel(.text)
        await vm.send()
        XCTAssertNil(vm.pendingSenderPrompt)
    }

    func testPromptNotShownAgainAfterActedOn() async {
        let links = InMemoryContactLinkStore()
        links.save(ContactLinkState(senderBindingID: "b1", contactStatus: .dismissed))
        let vm = makeVM(request: MockRequestService(created: smsRequest()), contactLinks: links)
        await vm.load()
        vm.selectChannel(.text)
        await vm.send()
        XCTAssertNil(vm.pendingSenderPrompt)
    }

    // MARK: Accept / skip / permission

    func testAcceptWithAuthorizedPresentsSheet() async {
        let links = InMemoryContactLinkStore()
        let vm = makeVM(request: MockRequestService(created: smsRequest()),
                        contacts: MockContactsService(status: .authorized),
                        contactLinks: links)
        await vm.load()
        vm.selectChannel(.text)
        await vm.send()
        await vm.acceptContactPrompt()
        XCTAssertEqual(vm.contactSheetSender?.bindingID, "b1")
        XCTAssertNil(vm.pendingSenderPrompt)
    }

    func testAcceptFromNotDeterminedRequestsAccessThenPresents() async {
        let contacts = MockContactsService(status: .notDetermined, grantResult: .authorized)
        let vm = makeVM(request: MockRequestService(created: smsRequest()), contacts: contacts)
        await vm.load()
        vm.selectChannel(.text)
        await vm.send()
        await vm.acceptContactPrompt()
        XCTAssertTrue(contacts.requestAccessCalled)
        XCTAssertNotNil(vm.contactSheetSender)
    }

    func testAcceptWhenDeniedShowsOptionalNoticeAndRecordsState() async {
        let links = InMemoryContactLinkStore()
        let contacts = MockContactsService(status: .notDetermined, grantResult: .denied)
        let vm = makeVM(request: MockRequestService(created: smsRequest()),
                        contacts: contacts, contactLinks: links)
        await vm.load()
        vm.selectChannel(.text)
        await vm.send()
        await vm.acceptContactPrompt()
        XCTAssertNil(vm.contactSheetSender)
        XCTAssertEqual(vm.contactPermissionDeniedSender?.bindingID, "b1")
        XCTAssertEqual(links.state(forBinding: "b1")?.contactStatus, .denied)
    }

    func testSaveButtonPresentsSheetWhilePromptStillShowing() async {
        // Regression: the alert's "Save" button calls beginSaveContact(for:)
        // with the captured sender while pendingSenderPrompt is still set. It
        // must present the sheet and must NOT be recorded as a skip.
        let links = InMemoryContactLinkStore()
        let vm = makeVM(request: MockRequestService(created: smsRequest()),
                        contacts: MockContactsService(status: .authorized), contactLinks: links)
        await vm.load()
        vm.selectChannel(.text)
        await vm.send()
        let sender = vm.pendingSenderPrompt!  // prompt is showing
        await vm.beginSaveContact(for: sender)
        XCTAssertEqual(vm.contactSheetSender?.bindingID, "b1")
        XCTAssertNil(vm.pendingSenderPrompt)
        XCTAssertNotEqual(links.state(forBinding: "b1")?.contactStatus, .notNow)
    }

    func testMarkPromptSkippedRecordsNotNow() async {
        let links = InMemoryContactLinkStore()
        let vm = makeVM(request: MockRequestService(created: smsRequest()), contactLinks: links)
        await vm.load()
        vm.selectChannel(.text)
        await vm.send()
        vm.markPromptSkipped(for: vm.pendingSenderPrompt!)
        XCTAssertNil(vm.pendingSenderPrompt)
        XCTAssertEqual(links.state(forBinding: "b1")?.contactStatus, .notNow)
    }

    func testSkipRecordsNotNow() async {
        let links = InMemoryContactLinkStore()
        let vm = makeVM(request: MockRequestService(created: smsRequest()), contactLinks: links)
        await vm.load()
        vm.selectChannel(.text)
        await vm.send()
        vm.skipContactPrompt()
        XCTAssertNil(vm.pendingSenderPrompt)
        XCTAssertEqual(links.state(forBinding: "b1")?.contactStatus, .notNow)
    }

    // MARK: Contact sheet outcomes

    func testContactSavedRecordsCreatedWithIdentifier() async {
        let links = InMemoryContactLinkStore()
        let vm = makeVM(request: MockRequestService(created: smsRequest()),
                        contacts: MockContactsService(status: .authorized), contactLinks: links)
        await vm.load()
        vm.selectChannel(.text)
        await vm.send()
        await vm.acceptContactPrompt()
        vm.contactSheetFinished(savedIdentifier: "ios-contact-42")
        let state = links.state(forBinding: "b1")
        XCTAssertEqual(state?.contactStatus, .created)
        XCTAssertEqual(state?.iosContactIdentifier, "ios-contact-42")
        XCTAssertNotNil(state?.createdAt)
        XCTAssertNil(vm.contactSheetSender)
    }

    func testContactSheetCancelRecordsDismissed() async {
        let links = InMemoryContactLinkStore()
        let vm = makeVM(request: MockRequestService(created: smsRequest()),
                        contacts: MockContactsService(status: .authorized), contactLinks: links)
        await vm.load()
        vm.selectChannel(.text)
        await vm.send()
        await vm.acceptContactPrompt()
        vm.contactSheetFinished(savedIdentifier: nil)
        XCTAssertEqual(links.state(forBinding: "b1")?.contactStatus, .dismissed)
    }

    // MARK: Mapping

    func testCreateResponseMapsSenderIdentity() {
        let dto = CreateRequestResponseDTO(
            request_id: "r1", channel: "sms", status: "scheduled", execute_at: Date(),
            credits_available: 2, cancelable: true,
            sender_identity: SenderIdentityDTO(
                sender_binding_id: "b9", sender_persona_key: "boss",
                sender_display_name: "Boss", sender_phone_e164: "+15551112222",
                contact_prompt_recommended: true)
        )
        let model = RequestSummary(dto: dto)
        XCTAssertEqual(model.senderIdentity?.bindingID, "b9")
        XCTAssertEqual(model.senderIdentity?.displayName, "Boss")
        XCTAssertTrue(model.senderIdentity?.contactPromptRecommended ?? false)
        XCTAssertTrue(model.senderIdentity?.canSaveContact ?? false)
    }

    func testHistoryMapsSenderSnapshotForReentry() {
        let dto = HistoryItemDTO(
            request_id: "r1", channel: "sms", template_label: "Boss — trip",
            requested_at: Date(), execute_at: Date(), final_status: "completed",
            cancelable: false, duration_seconds: nil,
            delivered_preview: "hi", sender_binding_id: "b3", sender_persona_key: "boss",
            sender_display_name: "Boss", sender_phone_e164: "+15553334444"
        )
        let entry = HistoryEntry(dto: dto)
        XCTAssertEqual(entry.senderIdentity?.bindingID, "b3")
        XCTAssertEqual(entry.senderIdentity?.phoneE164, "+15553334444")
        // History snapshots don't drive an automatic prompt.
        XCTAssertFalse(entry.senderIdentity?.contactPromptRecommended ?? true)
    }
}
