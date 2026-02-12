import React from "react";
import {
  StyleSheet,
  Text,
  View,
  ScrollView,
  ActivityIndicator,
  Platform,
  Pressable,
} from "react-native";
import { useQuery } from "@tanstack/react-query";
import { useLocalSearchParams, router } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import Colors from "@/constants/colors";
import SectionHeader from "@/components/SectionHeader";
import LineChart from "@/components/charts/LineChart";
import GroupedBarChart from "@/components/charts/GroupedBarChart";
import DonutChart from "@/components/charts/DonutChart";
import BarChart from "@/components/charts/BarChart";
import BudgetCard from "@/components/BudgetCard";
import { formatCrore, formatCroreShort, shortYear, getGrowthPercent } from "@/lib/format";

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
  taxBreakdown?: {
    incomeTax: { be: number; re: number; actual: number };
    corporateTax: { be: number; re: number; actual: number };
    gstCentral: { be: number; re: number; actual: number };
    customs: { be: number; re: number; actual: number };
    otherTax: { be: number; re: number; actual: number };
  };
}

const categoryConfig: Record<string, {
  title: string;
  icon: string;
  color: string;
}> = {
  tax_revenue: { title: "Tax Revenue", icon: "receipt", color: Colors.light.primary },
  non_tax_revenue: { title: "Non-Tax Revenue", icon: "cash", color: Colors.light.accent },
  capital_receipts: { title: "Capital Receipts", icon: "business", color: Colors.light.success },
};

export default function ReceiptDetailScreen() {
  const { category, name } = useLocalSearchParams<{ category: string; name: string }>();
  const insets = useSafeAreaInsets();
  const topPad = Platform.OS === "web" ? 67 : 0;

  const { data: allData, isLoading } = useQuery<BudgetYearData[]>({
    queryKey: ["/api/budget/all"],
  });

  if (isLoading) {
    return (
      <View style={[styles.loadingContainer, { paddingTop: topPad + insets.top }]}>
        <ActivityIndicator size="large" color={Colors.light.primary} />
      </View>
    );
  }

  const config = categoryConfig[category || ""] || { title: name || "Details", icon: "analytics", color: Colors.light.primary };
  const last10 = (allData || []).slice(-10);
  const last5 = (allData || []).slice(-5);
  const latest = allData && allData.length > 0 ? allData[allData.length - 1] : null;
  const prev = allData && allData.length > 1 ? allData[allData.length - 2] : null;

  const getVal = (d: BudgetYearData) => {
    if (category === "tax_revenue") return d.receipts.taxRevenue;
    if (category === "non_tax_revenue") return d.receipts.nonTaxRevenue;
    return d.receipts.capitalReceipts;
  };

  const latestVal = latest ? getVal(latest) : { be: 0, re: 0, actual: 0 };
  const prevVal = prev ? getVal(prev) : { be: 0, re: 0, actual: 0 };
  const growth = getGrowthPercent(latestVal.be, prevVal.be);

  return (
    <ScrollView
      style={[styles.container, { paddingTop: topPad }]}
      contentContainerStyle={{ paddingBottom: Platform.OS === "web" ? 34 : 100 }}
      showsVerticalScrollIndicator={false}
    >
      <View style={styles.header}>
        <Pressable onPress={() => router.back()} style={styles.backButton}>
          <Ionicons name="arrow-back" size={22} color={Colors.light.text} />
        </Pressable>
        <View style={styles.headerText}>
          <Text style={styles.pageTitle}>{config.title}</Text>
          <Text style={styles.pageSubtitle}>Detailed analysis across years</Text>
        </View>
      </View>

      <View style={styles.cardsRow}>
        <View style={styles.cardHalf}>
          <BudgetCard
            title={`Latest BE (${latest?.year || ""})`}
            value={formatCrore(latestVal.be)}
            icon={config.icon as any}
            iconColor={config.color}
            growth={growth}
            subtitle="Budget Estimate"
          />
        </View>
        <View style={styles.cardHalf}>
          <BudgetCard
            title="Share of Total"
            value={latest ? `${((latestVal.be / latest.receipts.revenueReceipts.be) * 100).toFixed(1)}%` : "N/A"}
            icon="pie-chart"
            iconColor={Colors.light.primaryLight}
            subtitle="of Revenue Receipts"
          />
        </View>
      </View>

      <SectionHeader title="BE vs RE vs Actual" subtitle="Last 5 years comparison" />
      <View style={styles.chartCard}>
        <GroupedBarChart
          data={last5.map((d) => {
            const v = getVal(d);
            return {
              label: shortYear(d.year),
              values: [
                { value: v.be, color: Colors.light.budgetColor, name: "Budget Est." },
                { value: v.re, color: Colors.light.revisedColor, name: "Revised Est." },
                { value: v.actual, color: Colors.light.actualColor, name: "Actual" },
              ],
            };
          })}
          height={220}
          formatValue={formatCroreShort}
          yAxisLabel="in Crores"
        />
      </View>

      <SectionHeader title="Trend Over Time" subtitle="Budget Estimates (last 10 years)" />
      <View style={styles.chartCard}>
        <LineChart
          labels={last10.map((d) => shortYear(d.year))}
          datasets={[
            {
              data: last10.map((d) => getVal(d).be),
              color: config.color,
              label: config.title,
            },
          ]}
          height={220}
          showArea
          formatValue={formatCroreShort}
          yAxisLabel="in Crores"
        />
      </View>

      <SectionHeader title="Year-on-Year Growth" subtitle="% change in Budget Estimate" />
      <View style={styles.chartCard}>
        <BarChart
          data={last10.slice(1).map((d, i) => {
            const prev = getVal(last10[i]).be;
            const curr = getVal(d).be;
            const growthPct = prev > 0 ? ((curr - prev) / prev) * 100 : 0;
            return {
              label: shortYear(d.year),
              value: growthPct,
              color: growthPct >= 0 ? Colors.light.success : Colors.light.danger,
            };
          })}
          height={180}
          barWidth={28}
          spacing={12}
          formatValue={(v) => `${v.toFixed(1)}%`}
        />
      </View>

      {category === "tax_revenue" && (
        <>
          <SectionHeader title="Tax Revenue Composition" subtitle={`FY ${latest?.year || ""} (BE)`} />
          <View style={styles.chartCard}>
            {latest?.taxBreakdown && (
              <DonutChart
                data={[
                  { label: "Income Tax", value: latest.taxBreakdown.incomeTax.be, color: Colors.light.chartColors[0] },
                  { label: "Corporate Tax", value: latest.taxBreakdown.corporateTax.be, color: Colors.light.chartColors[1] },
                  { label: "GST (Central)", value: latest.taxBreakdown.gstCentral.be, color: Colors.light.chartColors[2] },
                  { label: "Customs", value: latest.taxBreakdown.customs.be, color: Colors.light.chartColors[3] },
                  { label: "Other Tax", value: latest.taxBreakdown.otherTax.be, color: Colors.light.chartColors[4] },
                ]}
                size={140}
                centerLabel="Tax Rev."
                centerValue={formatCroreShort(latest.receipts.taxRevenue.be)}
              />
            )}
          </View>

          <SectionHeader title="Tax Component Trends" subtitle="BE over last 10 years" />
          <View style={styles.chartCard}>
            <LineChart
              labels={last10.map((d) => shortYear(d.year))}
              datasets={[
                { data: last10.map((d) => d.taxBreakdown?.incomeTax.be || 0), color: Colors.light.chartColors[0], label: "Income Tax" },
                { data: last10.map((d) => d.taxBreakdown?.corporateTax.be || 0), color: Colors.light.chartColors[1], label: "Corporate Tax" },
                { data: last10.map((d) => d.taxBreakdown?.gstCentral.be || 0), color: Colors.light.chartColors[2], label: "GST" },
                { data: last10.map((d) => d.taxBreakdown?.customs.be || 0), color: Colors.light.chartColors[3], label: "Customs" },
              ]}
              height={240}
              formatValue={formatCroreShort}
              yAxisLabel="in Crores"
            />
          </View>
        </>
      )}

      {category === "capital_receipts" && (
        <>
          <SectionHeader title="Capital Receipts Components" subtitle={`FY ${latest?.year || ""}`} />
          <View style={styles.chartCard}>
            {latest && (
              <DonutChart
                data={[
                  { label: "Recovery of Loans", value: Math.max(latest.receipts.recoveryOfLoans.be, 0), color: Colors.light.chartColors[2] },
                  { label: "Disinvestment", value: Math.max(latest.receipts.disinvestment.be, 0), color: Colors.light.chartColors[3] },
                ].filter(d => d.value > 0)}
                size={130}
                centerLabel="Capital"
                centerValue={formatCroreShort(latest.receipts.capitalReceipts.be)}
              />
            )}
          </View>

          <SectionHeader title="Component Trends" subtitle="BE over last 10 years" />
          <View style={styles.chartCard}>
            <LineChart
              labels={last10.map((d) => shortYear(d.year))}
              datasets={[
                { data: last10.map((d) => Math.max(d.receipts.recoveryOfLoans.be, 0)), color: Colors.light.chartColors[2], label: "Recovery of Loans" },
                { data: last10.map((d) => Math.max(d.receipts.disinvestment.be, 0)), color: Colors.light.chartColors[3], label: "Disinvestment" },
              ]}
              height={220}
              formatValue={formatCroreShort}
              yAxisLabel="in Crores"
            />
          </View>
        </>
      )}

      {category === "non_tax_revenue" && (
        <>
          <SectionHeader title="Non-Tax Revenue Trend" subtitle="BE, RE & Actual over last 10 years" />
          <View style={styles.chartCard}>
            <LineChart
              labels={last10.map((d) => shortYear(d.year))}
              datasets={[
                { data: last10.map((d) => d.receipts.nonTaxRevenue.be), color: Colors.light.budgetColor, label: "Budget Est." },
                { data: last10.map((d) => d.receipts.nonTaxRevenue.re), color: Colors.light.revisedColor, label: "Revised Est." },
                { data: last10.map((d) => d.receipts.nonTaxRevenue.actual), color: Colors.light.actualColor, label: "Actual" },
              ]}
              height={220}
              formatValue={formatCroreShort}
              yAxisLabel="in Crores"
            />
          </View>
        </>
      )}

      <SectionHeader title="Historical Data" subtitle="All years (Rs. Crore)" />
      <View style={styles.tableCard}>
        <View style={styles.tableHeader}>
          <Text style={[styles.tableCell, styles.tableHeaderText, { flex: 1.2 }]}>Year</Text>
          <Text style={[styles.tableCell, styles.tableHeaderText, { flex: 1 }]}>BE</Text>
          <Text style={[styles.tableCell, styles.tableHeaderText, { flex: 1 }]}>RE</Text>
          <Text style={[styles.tableCell, styles.tableHeaderText, { flex: 1 }]}>Actual</Text>
        </View>
        {(allData || []).slice().reverse().slice(0, 15).map((row) => {
          const v = getVal(row);
          return (
            <View key={row.year} style={styles.tableRow}>
              <Text style={[styles.tableCell, { flex: 1.2, fontFamily: "Inter_500Medium" }]}>{row.year}</Text>
              <Text style={[styles.tableCell, { flex: 1 }]}>{formatCroreShort(v.be)}</Text>
              <Text style={[styles.tableCell, { flex: 1 }]}>{v.re > 0 ? formatCroreShort(v.re) : "-"}</Text>
              <Text style={[styles.tableCell, { flex: 1 }]}>{v.actual > 0 ? formatCroreShort(v.actual) : "-"}</Text>
            </View>
          );
        })}
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.light.background },
  loadingContainer: { flex: 1, justifyContent: "center", alignItems: "center", backgroundColor: Colors.light.background },
  header: { flexDirection: "row", alignItems: "center", paddingHorizontal: 16, paddingBottom: 16, paddingTop: 8, gap: 12 },
  backButton: { width: 36, height: 36, borderRadius: 18, backgroundColor: Colors.light.surface, justifyContent: "center", alignItems: "center" },
  headerText: { flex: 1 },
  pageTitle: { fontSize: 22, fontFamily: "Inter_800ExtraBold", color: Colors.light.text },
  pageSubtitle: { fontSize: 12, fontFamily: "Inter_400Regular", color: Colors.light.textSecondary, marginTop: 2 },
  cardsRow: { flexDirection: "row", paddingHorizontal: 16, gap: 10, marginBottom: 4 },
  cardHalf: { flex: 1 },
  chartCard: {
    backgroundColor: Colors.light.surface,
    marginHorizontal: 16,
    borderRadius: 16,
    padding: 16,
    ...Platform.select({
      ios: { shadowColor: "#000", shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.06, shadowRadius: 8 },
      android: { elevation: 2 },
      web: { boxShadow: "0 2px 8px rgba(0,0,0,0.06)" },
    }),
  },
  tableCard: {
    marginHorizontal: 16,
    backgroundColor: Colors.light.surface,
    borderRadius: 16,
    overflow: "hidden",
    ...Platform.select({
      ios: { shadowColor: "#000", shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.06, shadowRadius: 8 },
      android: { elevation: 2 },
      web: { boxShadow: "0 2px 8px rgba(0,0,0,0.06)" },
    }),
  },
  tableHeader: { flexDirection: "row", backgroundColor: Colors.light.primary + "08", paddingHorizontal: 14, paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: Colors.light.border },
  tableHeaderText: { fontFamily: "Inter_600SemiBold", color: Colors.light.primary, fontSize: 11 },
  tableRow: { flexDirection: "row", paddingHorizontal: 14, paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: Colors.light.border },
  tableCell: { fontSize: 12, fontFamily: "Inter_400Regular", color: Colors.light.text },
});
