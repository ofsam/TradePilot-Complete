import { Modal, StyleSheet, Text, View } from "react-native"
import type { ScanProposal } from "../lib/types"
import { price } from "../lib/format"
import { colors } from "../lib/theme"
import { PrimaryButton, SecondaryButton } from "./ui"

type Props = {
  visible: boolean
  symbol: string
  proposal: ScanProposal | null
  busy?: boolean
  error?: string
  onCancel: () => void
  onConfirm: () => void
}

export function ConfirmSheet({ visible, symbol, proposal, busy, error, onCancel, onConfirm }: Props) {
  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onCancel}>
      <View style={styles.backdrop}>
        <View style={styles.sheet}>
          <Text style={styles.title}>Confirm order</Text>
          <Text style={styles.muted}>
            This sends a live or demo order on the cloud MT5 worker. Auto on the VPS is separate from this confirm.
          </Text>
          {proposal ? (
            <View style={styles.grid}>
              <Line label="Symbol" value={symbol} />
              <Line label="Side" value={proposal.direction} />
              <Line label="Entry" value={price(proposal.entry)} />
              <Line label="Stop" value={price(proposal.stop_loss)} />
              <Line label="Target" value={price(proposal.take_profit)} />
              {proposal.volume != null ? <Line label="Volume" value={String(proposal.volume)} /> : null}
            </View>
          ) : null}
          {error ? <Text style={styles.error}>{error}</Text> : null}
          <PrimaryButton label="Send order" onPress={onConfirm} busy={busy} disabled={!proposal} />
          <SecondaryButton label="Cancel" onPress={onCancel} disabled={busy} />
        </View>
      </View>
    </Modal>
  )
}

function Line({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.line}>
      <Text style={styles.lineLabel}>{label}</Text>
      <Text style={styles.lineValue}>{value}</Text>
    </View>
  )
}

const styles = StyleSheet.create({
  backdrop: { flex: 1, justifyContent: "flex-end", backgroundColor: "#00000088" },
  sheet: {
    backgroundColor: colors.card,
    borderTopLeftRadius: 16,
    borderTopRightRadius: 16,
    padding: 18,
    gap: 10,
    borderColor: colors.border,
    borderWidth: 1,
  },
  title: { color: colors.text, fontSize: 18, fontWeight: "700" },
  muted: { color: colors.muted, fontSize: 13, lineHeight: 18 },
  grid: { gap: 8, marginVertical: 6 },
  line: { flexDirection: "row", justifyContent: "space-between" },
  lineLabel: { color: colors.muted, fontSize: 13 },
  lineValue: { color: colors.text, fontWeight: "700", fontSize: 13 },
  error: { color: colors.danger, fontSize: 13 },
})
