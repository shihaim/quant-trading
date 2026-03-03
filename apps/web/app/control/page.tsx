import { PagePlaceholder } from "../../components/page-placeholder";

export default function ControlPage() {
  return (
    <PagePlaceholder
      title="Bot Control"
      ticketId="P1-FE6"
      dependency="V2 auth and /api/me/bot/* control endpoints"
      summary="This page route is ready, but the dedicated control workflow is intentionally deferred until authenticated user-scoped bot control APIs replace the legacy single-bot endpoints."
    />
  );
}
