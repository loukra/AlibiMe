#if canImport(SwiftUI)
import SwiftUI

/// Focused sheet for exact-time scheduling within the next 24 hours.
public struct ScheduleSheet: View {
    let timezone: String
    let onConfirm: (Date) -> Void
    let onCancel: () -> Void
    @State private var date: Date

    public init(timezone: String,
                onConfirm: @escaping (Date) -> Void,
                onCancel: @escaping () -> Void) {
        self.timezone = timezone
        self.onConfirm = onConfirm
        self.onCancel = onCancel
        // Default a few minutes out so the picker starts inside the valid window.
        _date = State(initialValue: Date().addingTimeInterval(600))
    }

    private var range: ClosedRange<Date> {
        let now = Date()
        return now.addingTimeInterval(60)...now.addingTimeInterval(24 * 3600)
    }

    public var body: some View {
        NavigationStack {
            VStack(alignment: .leading, spacing: Spacing.l) {
                Text("Pick a time within the next 24 hours.")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                DatePicker("Delivery time", selection: $date, in: range)
                    .datePickerStyle(.graphical)
                    .labelsHidden()
                Label("Times shown in \(timezone)", systemImage: "globe")
                    .font(.footnote)
                    .foregroundStyle(.secondary)
                Spacer()
                PrimaryButton("Schedule", systemImage: "calendar") { onConfirm(date) }
            }
            .padding(Spacing.l)
            .navigationTitle("Schedule")
            .bcInlineNavTitle()
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel", action: onCancel)
                }
            }
        }
    }
}

struct ScheduleSheet_Previews: PreviewProvider {
    static var previews: some View {
        ScheduleSheet(timezone: "Europe/Berlin", onConfirm: { _ in }, onCancel: {})
    }
}
#endif
