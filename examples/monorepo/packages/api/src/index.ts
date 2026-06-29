import express from "express";
import { authRouter } from "./auth";
import { projectsRouter } from "./routes";

const app = express();
app.use(express.json());

app.get("/health", (_req, res) => res.json({ status: "ok" }));
app.use("/auth", authRouter);
app.use("/projects", projectsRouter);

const PORT = Number(process.env.PORT ?? 4000);
app.listen(PORT, () => console.log(`API listening on :${PORT}`));

export { app };
