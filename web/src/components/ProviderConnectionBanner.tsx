import { useTranslation } from "react-i18next";
import StatusPill from "./StatusPill";

type Provider = "icloud" | "google";

type Props = {
  provider: Provider;
  authStatus: string;
  accountLabel?: string | null;
};

export default function ProviderConnectionBanner({
  provider,
  authStatus,
  accountLabel,
}: Props) {
  const { t } = useTranslation();
  const prefix = provider === "icloud" ? "userDetail.icloud" : "userDetail.google";

  const messageKey = `${prefix}Status_${authStatus}`;
  const message = t(messageKey, {
    account: accountLabel ?? "",
    defaultValue: t(`${prefix}Status_default`),
  });

  const borderClass =
    authStatus === "authorized"
      ? "border-emerald-700/50 bg-emerald-900/20"
      : authStatus === "not_linked"
        ? "border-slate-700 bg-slate-800/40"
        : "border-amber-700/50 bg-amber-900/20";

  return (
    <div className={`rounded-lg border px-4 py-3 mb-4 flex flex-wrap items-center gap-3 ${borderClass}`}>
      <StatusPill variant="auth" status={authStatus} />
      <div className="min-w-0 flex-1">
        <p className="text-sm text-slate-200 font-medium">{message}</p>
        {accountLabel && authStatus === "authorized" && (
          <p className="text-xs text-slate-400 mt-0.5 truncate" title={accountLabel}>
            {accountLabel}
          </p>
        )}
      </div>
    </div>
  );
}
