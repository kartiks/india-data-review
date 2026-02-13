import type { Express } from "express";
import { createServer, type Server } from "node:http";
import {
  budgetData,
  getAllYears,
  getBudgetByYear,
  getSectorTimeSeries,
  getAllSectors,
  getReceiptsTimeSeries,
  getExpenditureTimeSeries,
  getDeficitTimeSeries,
  getMacroTimeSeries,
  getTaxBreakdownTimeSeries,
  getDevolutionTimeSeries,
  getCSSTimeSeries,
  getSchemesBySection,
  getSchemeTimeSeries,
  getAllSchemeDirectory,
  getBudgetInsights,
} from "./data/budget-data";

export async function registerRoutes(app: Express): Promise<Server> {
  app.get("/api/budget/years", (_req, res) => {
    res.json(getAllYears());
  });

  app.get("/api/budget/year/:year", (req, res) => {
    const data = getBudgetByYear(req.params.year);
    if (!data) {
      return res.status(404).json({ error: "Year not found" });
    }
    res.json(data);
  });

  app.get("/api/budget/all", (_req, res) => {
    res.json(budgetData);
  });

  app.get("/api/budget/sectors", (_req, res) => {
    res.json(getAllSectors());
  });

  app.get("/api/budget/sector/:id", (req, res) => {
    const data = getSectorTimeSeries(req.params.id);
    res.json(data);
  });

  app.get("/api/budget/sector/:id/schemes", (req, res) => {
    const data = getSchemesBySection(req.params.id);
    res.json(data);
  });

  app.get("/api/budget/scheme/:id", (req, res) => {
    const data = getSchemeTimeSeries(req.params.id);
    res.json(data);
  });

  app.get("/api/budget/receipts", (_req, res) => {
    res.json(getReceiptsTimeSeries());
  });

  app.get("/api/budget/expenditure", (_req, res) => {
    res.json(getExpenditureTimeSeries());
  });

  app.get("/api/budget/deficit", (_req, res) => {
    res.json(getDeficitTimeSeries());
  });

  app.get("/api/budget/macro", (_req, res) => {
    res.json(getMacroTimeSeries());
  });

  app.get("/api/budget/tax-breakdown", (_req, res) => {
    res.json(getTaxBreakdownTimeSeries());
  });

  app.get("/api/budget/devolution", (_req, res) => {
    res.json(getDevolutionTimeSeries());
  });

  app.get("/api/budget/css", (_req, res) => {
    res.json(getCSSTimeSeries());
  });

  app.get("/api/budget/schemes/directory", (_req, res) => {
    res.json(getAllSchemeDirectory());
  });

  app.get("/api/budget/insights", (_req, res) => {
    res.json(getBudgetInsights());
  });

  app.get("/api/budget/overview", (_req, res) => {
    const overview = budgetData.map((d) => ({
      year: d.year,
      receipts: d.receipts.revenueReceipts.be,
      expenditure: d.expenditure.total.be,
      fiscalDeficit: d.deficit.fiscal.be,
      fiscalDeficitPercGDP: d.deficit.fiscalAsPercentGDP.be,
      gdp: d.gdp,
      gdpGrowthRate: d.macroeconomic.gdpGrowthRate,
      gdpPerCapita: d.macroeconomic.gdpPerCapita,
      inflationCPI: d.macroeconomic.inflationCPI,
    }));
    res.json(overview);
  });

  const httpServer = createServer(app);
  return httpServer;
}
