import { Route, Routes } from "react-router-dom";
import Layout from "./components/Layout.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import Findings from "./pages/Findings.jsx";
import FindingDetail from "./pages/FindingDetail.jsx";
import Help from "./pages/Help.jsx";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="findings" element={<Findings />} />
        <Route path="findings/:uid" element={<FindingDetail />} />
        <Route path="help" element={<Help />} />
        <Route path="*" element={<p className="empty">Page not found.</p>} />
      </Route>
    </Routes>
  );
}
