import XCTest
@testable import BelievableCall

final class MappingTests: XCTestCase {
    func testChannelWireMapping() {
        XCTAssertEqual(Channel.call.wireValue, "call")
        XCTAssertEqual(Channel.text.wireValue, "sms")
        XCTAssertEqual(Channel(wireValue: "sms"), .text)
        XCTAssertEqual(Channel(wireValue: "call"), .call)
        XCTAssertNil(Channel(wireValue: "fax"))
    }

    func testTimingDelayAndSchedule() {
        XCTAssertEqual(TimingOption.now.delaySeconds, 0)
        XCTAssertEqual(TimingOption.in30Seconds.delaySeconds, 30)
        XCTAssertEqual(TimingOption.in5Minutes.delaySeconds, 300)
        XCTAssertNil(TimingOption.schedule(Date()).delaySeconds)
        let date = Date().addingTimeInterval(600)
        XCTAssertEqual(TimingOption.schedule(date).scheduledAt, date)
        XCTAssertNil(TimingOption.now.scheduledAt)
    }

    func testRequestStatusMappingAndLiveness() {
        XCTAssertTrue(RequestStatus(wireValue: "scheduled").isLive)
        XCTAssertTrue(RequestStatus(wireValue: "active").isLive)
        XCTAssertTrue(RequestStatus(wireValue: "provider_accepted").isLive)
        XCTAssertTrue(RequestStatus(wireValue: "completed").isTerminal)
        XCTAssertTrue(RequestStatus(wireValue: "canceled").isTerminal)
        XCTAssertEqual(RequestStatus(wireValue: "nonsense"), .unknown)
    }

    func testTemplateMappingFromDTO() {
        let dto = TemplateOutDTO(
            id: "t1", code: "boss_travel_assignment", display_name: "Boss — trip",
            description: "desc", category: "work", caller_persona: "boss",
            reason_code: "travel_assignment_abroad",
            sender_persona_key: "boss", sender_display_name: "Boss", supports_contact_save: true,
            is_custom: false,
            supported_channels: ["call", "sms"],
            call_max_duration_seconds: 60, preview_opening_line: "hi", preview_sms_body: "yo"
        )
        let model = TemplateSummary(dto: dto)
        XCTAssertEqual(model.category, .work)
        XCTAssertEqual(model.supportedChannels, [.call, .text])
        XCTAssertTrue(model.supports(.call))
        XCTAssertEqual(model.preview(for: .text), "yo")
        XCTAssertEqual(model.senderPersonaKey, "boss")
        XCTAssertEqual(model.senderDisplayName, "Boss")
        XCTAssertTrue(model.supportsContactSave)
        XCTAssertFalse(model.isCustom)
    }

    func testUnknownCategoryFallsBack() {
        XCTAssertEqual(TemplateCategory(wireValue: "mystery"), .social)
    }

    func testCreateRequestBodyContainsNoDestinationNumber() throws {
        // The load-bearing rule: the request body must never carry a target
        // number. Only the allowed fields are present.
        let draft = RequestDraft(templateID: "tpl-1", channel: .call, timing: .in30Seconds,
                                 clientRequestID: "crid-1")
        let data = try BCCoding.encoder.encode(draft.toBody())
        let json = try JSONSerialization.jsonObject(with: data) as! [String: Any]
        let keys = Set(json.keys)
        XCTAssertEqual(keys, ["client_request_id", "template_id", "channel", "delay_seconds"])
        // Explicitly assert no destination-number smuggling keys exist.
        for forbidden in ["to", "phone_number", "target", "destination", "number"] {
            XCTAssertFalse(keys.contains(forbidden), "body must not contain \(forbidden)")
        }
        XCTAssertEqual(json["channel"] as? String, "call")
        XCTAssertEqual(json["delay_seconds"] as? Int, 30)
    }

    func testCreateRequestBodyForScheduleUsesScheduledAt() throws {
        let date = Date().addingTimeInterval(3600)
        let draft = RequestDraft(templateID: "tpl-1", channel: .text, timing: .schedule(date))
        let data = try BCCoding.encoder.encode(draft.toBody())
        let json = try JSONSerialization.jsonObject(with: data) as! [String: Any]
        XCTAssertNotNil(json["scheduled_at"])
        XCTAssertEqual(json["channel"] as? String, "sms")
        // delay_seconds is nil for exact-time scheduling, so the encoder omits
        // the key entirely (exactly one of delay/scheduled_at is sent).
        XCTAssertNil(json["delay_seconds"])
    }

    func testProfileMappingIncludesActiveRequest() {
        let dto = MeResponseDTO(
            id: "u1", locale: "en", timezone: "UTC", display_name: "Sam",
            phone_number_masked: "+14******123", credits_available: 2,
            active_entitlements: [.init(plan_code: "free", status: "active")],
            active_request: .init(request_id: "r1", channel: "call", status: "scheduled",
                                  execute_at: "2026-06-13T14:37:59.855827Z")
        )
        let profile = UserProfile(dto: dto)
        XCTAssertEqual(profile.displayName, "Sam")
        XCTAssertEqual(profile.entitlements.creditsAvailable, 2)
        XCTAssertEqual(profile.activeRequest?.id, "r1")
        XCTAssertEqual(profile.activeRequest?.channel, .call)
        XCTAssertTrue(profile.phone.isVerified)
    }

    func testSecondsRemainingNeverNegative() {
        let past = RequestSummary(id: "r", channel: .call, status: .scheduled, scheduledKind: nil,
                                  executeAt: Date().addingTimeInterval(-100), requestedAt: nil,
                                  cancelable: true, lastErrorCode: nil)
        XCTAssertEqual(past.secondsRemaining(), 0)
    }
}
