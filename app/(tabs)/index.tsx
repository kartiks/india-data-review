import React, { useState } from "react";
import {
  StyleSheet,
  Text,
  View,
  ScrollView,
  ActivityIndicator,
  Platform,
  Pressable,
  RefreshControl,
} from "react-native";
import { useQuery } from "@tanstack/react-query";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { router } from "expo-router";
import Colors from "@/constants/colors";
import BudgetCard from "@/components/BudgetCard";
import SectionHeader from "@/components/SectionHeader";
import LineChart from "@/components/charts/LineChart";
import DonutChart from "@/components/charts/DonutChart";
import { formatCrore, formatCroreShort, formatPercent, shortYear, getGrowthPercent } from "@/lib/format";

interface OverviewItem {
  year: string;
  receipts: number;
  expenditure: number;
  fiscalDeficit: number;
  fiscalDeficitPercGDP: number;
  gdp: number;
  gdpGrowthRate: number;
  gdpPerCapita: number;
  inflationCPI: number;
}

interface BudgetYearData {
  year: string;
  receipts: {
    revenueReceipts: { be: number; re: number; actual: number };
    taxRevenue: { be: number; re: number; actual: number };
    nonTaxRevenue: { be: number; re: number; actual: number };
    capitalReceipts: { be: number; re: number; actual: number };
  };
  expenditure: {
    total: { be: number; re: number; actual: number };
    revenueExpenditure: { be: number; re: number; actual: number };
    capitalExpenditure: { be: number; re: number; actual: number };
    interestPayments: { be: number; re: number; actual: number };
    subsidies: { be: number; re: number; actual: number };
  };
  deficit: {
    fiscal: { be: number; re: number; actual: number };
    fiscalAsPercentGDP: { be: number; re: number; actual: number };
  };
  sectors: Array<{ name: string; id: string; allocation: { be: number } }>;
}

export default function OverviewScreen() {
  const insets = useSafeAreaInsets();
  const topPad = Platform.OS === "web" ? 67 : 0;

  const { data: overviewData, isLoading, refetch } = useQuery<OverviewItem[]>({
    queryKey: ["/api/budget/overview"],
  });

  const latestYear = overviewData ? overviewData[overviewData.length - 1] : null;
  const prevYear = overviewData && overviewData.length > 1 ? overviewData[overviewData.length - 2] : null;

  const { data: latestDetail } = useQuery<BudgetYearData>({
    queryKey: ["/api/budget/year", latestYear?.year || "2026-27"],
    enabled: !!latestYear,
  });

  if (isLoading) {
    return (
      <View style={[styles.loadingContainer, { paddingTop: topPad + insets.top }]}>
        <ActivityIndicator size="large" color={Colors.light.primary} />
        <Text style={styles.loadingText}>Loading budget data...</Text>
      </View>
    );
  }

  const receiptGrowth = latestYear && prevYear
    ? getGrowthPercent(latestYear.receipts, prevYear.receipts) : 0;
  const expenditureGrowth = latestYear && prevYear
    ? getGrowthPercent(latestYear.expenditure, prevYear.expenditure) : 0;

  const receiptsChartData = (overviewData || []).slice(-10);
  const expenditureChartData = (overviewData || []).slice(-10);

  const receiptBreakdown = latestDetail ? [
    { label: "Tax Revenue", value: latestDetail.receipts.taxRevenue.be, color: Colors.light.primary },
    { label: "Non-Tax Revenue", value: latestDetail.receipts.nonTaxRevenue.be, color: Colors.light.accent },
    { label: "Capital Receipts", value: latestDetail.receipts.capitalReceipts.be, color: Colors.light.success },
  ] : [];

  const expenditureBreakdown = latestDetail ? [
    { label: "Revenue Exp.", value: latestDetail.expenditure.revenueExpenditure.be, color: Colors.light.danger },
    { label: "Capital Exp.", value: latestDetail.expenditure.capitalExpenditure.be, color: Colors.light.primaryLight },
  ] : [];

  return (
    <ScrollView
      style={[styles.container, { paddingTop: topPad }]}
      contentContainerStyle={{ paddingBottom: Platform.OS === "web" ? 34 : 100 }}
      refreshControl={
        <RefreshControl refreshing={false} onRefresh={() => refetch()} />
      }
      showsVerticalScrollIndicator={false}
    >
      <View style={[styles.heroSection, { paddingTop: insets.top + 16 }]}>
        <View style={styles.heroContent}>
          <Text style={styles.heroTitle}>India Budget</Text>
          <Text style={styles.heroSubtitle}>
            Union Budget {latestYear?.year || "2026-27"} Overview
          </Text>
        </View>
        <View style={styles.heroIndicator}>
          <View style={styles.flagStripe}>
            <View style={[styles.stripe, { backgroundColor: "#FF9933" }]} />
            <View style={[styles.stripe, { backgroundColor: "#FFFFFF" }]} />
            <View style={[styles.stripe, { backgroundColor: "#138808" }]} />
          </View>
        </View>
      </View>

      <View style={styles.cardsRow}>
        <View style={styles.cardHalf}>
          <BudgetCard
            title="Total Receipts (BE)"
            value={formatCrore(latestYear?.receipts || 0)}
            icon="arrow-down-circle"
            iconColor={Colors.light.success}
            growth={receiptGrowth}
            subtitle={`FY ${latestYear?.year || ""}`}
          />
        </View>
        <View style={styles.cardHalf}>
          <BudgetCard
            title="Total Expenditure (BE)"
            value={formatCrore(latestYear?.expenditure || 0)}
            icon="arrow-up-circle"
            iconColor={Colors.light.danger}
            growth={expenditureGrowth}
            subtitle={`FY ${latestYear?.year || ""}`}
          />
        </View>
      </View>

      <View style={styles.cardsRow}>
        <View style={styles.cardHalf}>
          <BudgetCard
            title="Fiscal Deficit (BE)"
            value={formatCrore(latestYear?.fiscalDeficit || 0)}
            icon="trending-down"
            iconColor={Colors.light.accent}
            subtitle={`${latestYear?.fiscalDeficitPercGDP || 0}% of GDP`}
          />
        </View>
        <View style={styles.cardHalf}>
          <BudgetCard
            title="GDP"
            value={formatCrore(latestYear?.gdp || 0)}
            icon="stats-chart"
            iconColor={Colors.light.primaryLight}
            subtitle={`FY ${latestYear?.year || ""}`}
          />
        </View>
      </View>

      <SectionHeader title="Macro Indicators" subtitle={`FY ${latestYear?.year || ""}`} />
      <View style={styles.cardsRow}>
        <View style={styles.cardHalf}>
          <BudgetCard
            title="GDP Growth Rate"
            value={formatPercent(latestYear?.gdpGrowthRate || 0)}
            icon="trending-up"
            iconColor={Colors.light.success}
            growth={latestYear && prevYear ? latestYear.gdpGrowthRate - prevYear.gdpGrowthRate : undefined}
            subtitle={`FY ${latestYear?.year || ""}`}
          />
        </View>
        <View style={styles.cardHalf}>
          <BudgetCard
            title="GDP Per Capita"
            value={`\u20B9${((latestYear?.gdpPerCapita || 0)).toLocaleString("en-IN")}`}
            icon="person"
            iconColor={Colors.light.primaryLight}
            subtitle={`FY ${latestYear?.year || ""}`}
          />
        </View>
      </View>
      <View style={styles.cardsRow}>
        <View style={styles.cardHalf}>
          <BudgetCard
            title="Inflation (CPI)"
            value={formatPercent(latestYear?.inflationCPI || 0)}
            icon={latestYear && prevYear && latestYear.inflationCPI > prevYear.inflationCPI ? "arrow-up" : "arrow-down"}
            iconColor={latestYear && prevYear && latestYear.inflationCPI > prevYear.inflationCPI ? Colors.light.danger : Colors.light.success}
            growth={latestYear && prevYear ? latestYear.inflationCPI - prevYear.inflationCPI : undefined}
            subtitle={`FY ${latestYear?.year || ""}`}
          />
        </View>
      </View>

      <SectionHeader title="Receipts vs Expenditure" subtitle="Budget Estimates (last 10 years)" />
      <View style={styles.chartCard}>
        <LineChart
          labels={receiptsChartData.map((d) => shortYear(d.year))}
          datasets={[
            {
              data: receiptsChartData.map((d) => d.receipts),
              color: Colors.light.success,
              label: "Receipts",
            },
            {
              data: expenditureChartData.map((d) => d.expenditure),
              color: Colors.light.danger,
              label: "Expenditure",
            },
          ]}
          height={220}
          showArea
          formatValue={formatCroreShort}
          yAxisLabel="₹ Crore"
        />
      </View>

      {latestDetail && (
        <>
          <SectionHeader
            title="Receipt Breakdown"
            subtitle={`FY ${latestDetail.year}`}
          />
          <View style={styles.chartCard}>
            <DonutChart
              data={receiptBreakdown}
              size={140}
              centerLabel="Total"
              centerValue={formatCroreShort(latestDetail.receipts.revenueReceipts.be)}
            />
          </View>

          <SectionHeader
            title="Expenditure Split"
            subtitle={`FY ${latestDetail.year}`}
          />
          <View style={styles.chartCard}>
            <DonutChart
              data={expenditureBreakdown}
              size={140}
              centerLabel="Total"
              centerValue={formatCroreShort(latestDetail.expenditure.total.be)}
            />
          </View>

          <SectionHeader
            title="Sector Allocations"
            subtitle={`Top sectors by Budget Estimate`}
            onPress={() => router.push("/(tabs)/expenditure")}
          />
          <View style={styles.sectorList}>
            {latestDetail.sectors
              .sort((a, b) => b.allocation.be - a.allocation.be)
              .slice(0, 5)
              .map((sector, i) => (
                <Pressable
                  key={sector.id}
                  style={styles.sectorItem}
                  onPress={() => router.push({ pathname: "/sector/[id]", params: { id: sector.id, name: sector.name } })}
                >
                  <View style={styles.sectorRank}>
                    <Text style={styles.sectorRankText}>{i + 1}</Text>
                  </View>
                  <View style={styles.sectorInfo}>
                    <Text style={styles.sectorName}>{sector.name}</Text>
                    <Text style={styles.sectorValue}>{formatCrore(sector.allocation.be)}</Text>
                  </View>
                  <Ionicons name="chevron-forward" size={16} color={Colors.light.textSecondary} />
                </Pressable>
              ))}
          </View>
        </>
      )}

      <SectionHeader title="Fiscal Deficit Trend" subtitle="% of GDP (Budget Estimates)" />
      <View style={styles.chartCard}>
        <LineChart
          labels={(overviewData || []).slice(-15).map((d) => shortYear(d.year))}
          datasets={[
            {
              data: (overviewData || []).slice(-15).map((d) => d.fiscalDeficitPercGDP),
              color: Colors.light.accent,
              label: "Fiscal Deficit % GDP",
            },
          ]}
          height={200}
          showArea
          formatValue={(v) => `${v.toFixed(1)}%`}
          yAxisLabel="% of GDP"
        />
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.light.background,
  },
  loadingContainer: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    backgroundColor: Colors.light.background,
    gap: 12,
  },
  loadingText: {
    fontSize: 14,
    fontFamily: "Inter_500Medium",
    color: Colors.light.textSecondary,
  },
  heroSection: {
    paddingHorizontal: 16,
    paddingBottom: 16,
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  heroContent: {
    flex: 1,
  },
  heroTitle: {
    fontSize: 28,
    fontFamily: "Inter_800ExtraBold",
    color: Colors.light.text,
  },
  heroSubtitle: {
    fontSize: 14,
    fontFamily: "Inter_400Regular",
    color: Colors.light.textSecondary,
    marginTop: 4,
  },
  heroIndicator: {
    width: 36,
    height: 36,
    borderRadius: 18,
    overflow: "hidden",
    borderWidth: 1,
    borderColor: Colors.light.border,
  },
  flagStripe: {
    flex: 1,
  },
  stripe: {
    flex: 1,
  },
  cardsRow: {
    flexDirection: "row",
    paddingHorizontal: 16,
    gap: 10,
    marginBottom: 10,
  },
  cardHalf: {
    flex: 1,
  },
  chartCard: {
    backgroundColor: Colors.light.surface,
    marginHorizontal: 16,
    borderRadius: 16,
    padding: 16,
    ...Platform.select({
      ios: {
        shadowColor: "#000",
        shadowOffset: { width: 0, height: 2 },
        shadowOpacity: 0.06,
        shadowRadius: 8,
      },
      android: { elevation: 2 },
      web: { boxShadow: "0 2px 8px rgba(0,0,0,0.06)" },
    }),
  },
  sectorList: {
    marginHorizontal: 16,
    backgroundColor: Colors.light.surface,
    borderRadius: 16,
    overflow: "hidden",
    ...Platform.select({
      ios: {
        shadowColor: "#000",
        shadowOffset: { width: 0, height: 2 },
        shadowOpacity: 0.06,
        shadowRadius: 8,
      },
      android: { elevation: 2 },
      web: { boxShadow: "0 2px 8px rgba(0,0,0,0.06)" },
    }),
  },
  sectorItem: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 16,
    paddingVertical: 14,
    borderBottomWidth: 1,
    borderBottomColor: Colors.light.border,
    gap: 12,
  },
  sectorRank: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: Colors.light.primary + "10",
    justifyContent: "center",
    alignItems: "center",
  },
  sectorRankText: {
    fontSize: 12,
    fontFamily: "Inter_700Bold",
    color: Colors.light.primary,
  },
  sectorInfo: {
    flex: 1,
  },
  sectorName: {
    fontSize: 14,
    fontFamily: "Inter_500Medium",
    color: Colors.light.text,
  },
  sectorValue: {
    fontSize: 12,
    fontFamily: "Inter_400Regular",
    color: Colors.light.textSecondary,
    marginTop: 2,
  },
});
