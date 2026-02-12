import React, { useState } from "react";
import {
  StyleSheet,
  Text,
  View,
  ScrollView,
  ActivityIndicator,
  Platform,
} from "react-native";
import { useQuery } from "@tanstack/react-query";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import Colors from "@/constants/colors";
import SectionHeader from "@/components/SectionHeader";
import YearSelector from "@/components/YearSelector";
import LineChart from "@/components/charts/LineChart";
import BarChart from "@/components/charts/BarChart";
import DonutChart from "@/components/charts/DonutChart";
import BudgetCard from "@/components/BudgetCard";
import { formatCrore, formatCroreShort, shortYear } from "@/lib/format";

interface BudgetYearData {
  year: string;
  receipts: {
    total: { be: number; re: number; actual: number };
    revenueReceipts: { be: number; re: number; actual: number };
    taxRevenue: { be: number; re: number; actual: number };
    nonTaxRevenue: { be: number; re: number; actual: number };
    capitalReceipts: { be: number; re: number; actual: number };
    recoveryOfLoans: { be: number; re: number; actual: number };
    disinvestment: { be: number; re: number; actual: number };
    borrowings: { be: number; re: number; actual: number };
  };
}

export default function RevenueScreen() {
  const insets = useSafeAreaInsets();
  const topPad = Platform.OS === "web" ? 67 : 0;

  const { data: allData, isLoading } = useQuery<BudgetYearData[]>({
    queryKey: ["/api/budget/all"],
  });

  const years = (allData || []).map((d) => d.year);
  const [selectedYear, setSelectedYear] = useState("2026-27");

  const yearData = (allData || []).find((d) => d.year === selectedYear);

  if (isLoading) {
    return (
      <View style={[styles.loadingContainer, { paddingTop: topPad + insets.top }]}>
        <ActivityIndicator size="large" color={Colors.light.primary} />
      </View>
    );
  }

  const last10 = (allData || []).slice(-10);

  const beReActualData = yearData
    ? [
        { label: "Budget Est.", value: yearData.receipts.revenueReceipts.be, color: Colors.light.budgetColor },
        { label: "Revised Est.", value: yearData.receipts.revenueReceipts.re, color: Colors.light.revisedColor },
        { label: "Actual", value: yearData.receipts.revenueReceipts.actual, color: Colors.light.actualColor },
      ].filter((d) => d.value > 0)
    : [];

  const breakdownData = yearData
    ? [
        { label: "Tax Revenue", value: yearData.receipts.taxRevenue.be, color: Colors.light.chartColors[0] },
        { label: "Non-Tax Revenue", value: yearData.receipts.nonTaxRevenue.be, color: Colors.light.chartColors[1] },
      ]
    : [];

  const capitalBreakdown = yearData
    ? [
        { label: "Recovery of Loans", value: yearData.receipts.recoveryOfLoans.be, color: Colors.light.chartColors[2] },
        { label: "Disinvestment", value: yearData.receipts.disinvestment.be, color: Colors.light.chartColors[3] },
      ].filter((d) => d.value > 0)
    : [];

  return (
    <ScrollView
      style={[styles.container, { paddingTop: topPad }]}
      contentContainerStyle={{ paddingBottom: Platform.OS === "web" ? 34 : 100 }}
      showsVerticalScrollIndicator={false}
    >
      <View style={{ paddingTop: insets.top + 8 }}>
        <View style={styles.pageHeader}>
          <Text style={styles.pageTitle}>Revenue Analysis</Text>
          <Text style={styles.pageSubtitle}>Receipts breakdown across years</Text>
        </View>

        <YearSelector years={years} selected={selectedYear} onSelect={setSelectedYear} />

        {yearData && (
          <>
            <View style={styles.cardsRow}>
              <View style={styles.cardHalf}>
                <BudgetCard
                  title="Revenue Receipts"
                  value={formatCrore(yearData.receipts.revenueReceipts.be)}
                  icon="wallet"
                  iconColor={Colors.light.success}
                  subtitle="Budget Estimate"
                />
              </View>
              <View style={styles.cardHalf}>
                <BudgetCard
                  title="Capital Receipts"
                  value={formatCrore(yearData.receipts.capitalReceipts.be)}
                  icon="business"
                  iconColor={Colors.light.primaryLight}
                  subtitle="Budget Estimate"
                />
              </View>
            </View>

            <SectionHeader title="BE vs RE vs Actual" subtitle={`FY ${selectedYear}`} />
            <View style={styles.chartCard}>
              <BarChart
                data={beReActualData}
                barWidth={60}
                spacing={20}
                formatValue={formatCroreShort}
                height={180}
              />
            </View>

            <SectionHeader title="Revenue Receipts Breakdown" subtitle={`FY ${selectedYear}`} />
            <View style={styles.chartCard}>
              <DonutChart
                data={breakdownData}
                size={140}
                centerLabel="Revenue"
                centerValue={formatCroreShort(yearData.receipts.revenueReceipts.be)}
              />
            </View>

            {capitalBreakdown.length > 0 && (
              <>
                <SectionHeader title="Capital Receipts" subtitle={`FY ${selectedYear}`} />
                <View style={styles.chartCard}>
                  <DonutChart
                    data={capitalBreakdown}
                    size={130}
                    centerLabel="Capital"
                    centerValue={formatCroreShort(yearData.receipts.capitalReceipts.be)}
                  />
                </View>
              </>
            )}
          </>
        )}

        <SectionHeader title="Revenue Trend" subtitle="Tax vs Non-Tax (last 10 years BE)" />
        <View style={styles.chartCard}>
          <LineChart
            labels={last10.map((d) => shortYear(d.year))}
            datasets={[
              {
                data: last10.map((d) => d.receipts.taxRevenue.be),
                color: Colors.light.primary,
                label: "Tax Revenue",
              },
              {
                data: last10.map((d) => d.receipts.nonTaxRevenue.be),
                color: Colors.light.accent,
                label: "Non-Tax Revenue",
              },
            ]}
            height={220}
            showArea
          />
        </View>

        <SectionHeader title="Total Receipts Over Time" subtitle="BE, RE & Actuals" />
        <View style={styles.chartCard}>
          <LineChart
            labels={last10.map((d) => shortYear(d.year))}
            datasets={[
              {
                data: last10.map((d) => d.receipts.revenueReceipts.be),
                color: Colors.light.budgetColor,
                label: "Budget Est.",
              },
              {
                data: last10.map((d) => d.receipts.revenueReceipts.re),
                color: Colors.light.revisedColor,
                label: "Revised Est.",
              },
              {
                data: last10.map((d) => d.receipts.revenueReceipts.actual),
                color: Colors.light.actualColor,
                label: "Actual",
              },
            ]}
            height={220}
            showArea={false}
          />
        </View>
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
  },
  pageHeader: {
    paddingHorizontal: 16,
    paddingBottom: 12,
  },
  pageTitle: {
    fontSize: 24,
    fontFamily: "Inter_800ExtraBold",
    color: Colors.light.text,
  },
  pageSubtitle: {
    fontSize: 13,
    fontFamily: "Inter_400Regular",
    color: Colors.light.textSecondary,
    marginTop: 4,
  },
  cardsRow: {
    flexDirection: "row",
    paddingHorizontal: 16,
    gap: 10,
    marginBottom: 4,
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
});
