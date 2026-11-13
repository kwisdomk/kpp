import App from "./App";
import ErrorPage from "./components/ErrorPage";
import { errorForPath } from "./errorStates";

export default function WorkspaceRouter() {
  const error = errorForPath(window.location.pathname);
  return error ? <ErrorPage kind={error} /> : <App />;
}
