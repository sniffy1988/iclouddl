import StatusPill from "./StatusPill";

type Props = {
  authorized: boolean;
  authStatus?: string;
};

/** Auth label only — use format2faDaysLeft in the 2FA left column for countdown. */
export default function IcloudAuthBadge({ authorized, authStatus }: Props) {
  const status = authStatus ?? (authorized ? "authorized" : "not_authorized");
  return <StatusPill variant="auth" status={status} />;
}
