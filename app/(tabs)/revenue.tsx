import React, { useState } from "react";
import {
  StyleSheet,
  Text,
  View,
  ScrollView,
  ActivityIndicator,
  Platform,
  TouchableOpacity,
} from "react-native";
import { useQuery } from "@tanstack/react-query";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import Colors from "@/constants/colors";
import SectionHeader from "@/components/SectionHeader";
import YearSelector from "@/components/YearSelector";
import LineChart from "@/components/charts/LineChart";
import GroupedBarChart from "@/components/charts/GroupedBarChart";
import DonutChart from "@/components/charts/DonutChart";
import BudgetCard from "@/components/BudgetCard";
import { formatCrore, formatCroreShort, shortYear } from "@/lib/format";

interface BERealActual {
  be: number;
  re: number;
  actual: number;
}

interface BudgetYearData {
  year: string;
  receipts: {
    total: BERealActual;
    revenueReceipts: BERealActual;
    taxRevenue: BERealActual;
    nonTaxRevenue: BERealActual;
    capitalReceipts: BERealActual;
    recoveryOfLoans: BERealActual;
    disinvestment: BERealActual;
    borrowings: BERealActual;
  };
  taxBreakdown?: {
    incomeTax: BERealActual;
    corporateTax: BERealActual;
    gstCentral: BERealActual;
    customs: BERealActual;
    otherTax: BERealActual;
  };
}

interface ReceiptCategoryItem {
  label: string;
  category: string;
  value: number;
  color: string;
  icon: keyof typeof Ionicons.glyphMap;
}

export default function RevenueScreen() {
  const insets = useSafeAreaInsets();
  const topPad = Platform.OS === "web" ? 67 : 0;
  const router = useRouter();

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
  const last5 = (allData || []).slice(-5);

  const groupedBarData = last5.map((d) => ({
    label: shortYear(d.year),
    values: [
      { value: d.receipts.revenueReceipts.be, color: Colors.light.budgetColor, name: "Budget Est." },
      { value: d.receipts.revenueReceipts.re, color: Colors.light.revisedColor, name: "Revised Est." },
      { value: d.receipts.revenueReceipts.actual, color: Colors.light.actualColor, name: "Actual" },
    ].filter((v) => v.value > 0),
  }));

  const receiptCategories: ReceiptCategoryItem[] = yearData
    ? [
        {
          label: "Tax Revenue",
          category: "tax_revenue",
          value: yearData.receipts.taxRevenue.be,
          color: Colors.light.chartColors[0],
          icon: "receipt",
        },
        {
          label: "Non-Tax Revenue",
          category: "non_tax_revenue",
          value: yearData.receipts.nonTaxRevenue.be,
          color: Colors.light.chartColors[1],
          icon: "cash",
        },
        {
          label: "Capital Receipts",
          category: "capital_receipts",
          value: yearData.receipts.capitalReceipts.be,
          color: Colors.light.chartColors[2],
          icon: "business",
        },
      ]
    : [];

  const totalReceipts = receiptCategories.reduce((s, c) => s + c.value, 0);

  const taxBreakdownData =
    yearData?.taxBreakdown
      ? [
          { label: "Income Tax", value: yearData.taxBreakdown.incomeTax.be, color: Colors.light.chartColors[0] },
          { label: "Corporate Tax", value: yearData.taxBreakdown.corporateTax.be, color: Colors.light.chartColors[1] },
          { label: "GST (Central)", value: yearData.taxBreakdown.gstCentral.be, color: Colors.light.chartColors[2] },
          { label: "Customs", value: yearData.taxBreakdown.customs.be, color: Colors.light.chartColors[3] },
          { label: "Other Tax", value: yearData.taxBreakdown.otherTax.be, color: Colors.light.chartColors[4] },
        ].filter((d) => d.value > 0)
      : [];

  const capitalItems = yearData
    ? [
        {
          label: "Recovery of Loans",
          data: yearData.receipts.recoveryOfLoans,
          color: Colors.light.chartColors[2],
          icon: "return-down-back" as keyof typeof Ionicons.glyphMap,
        },
        {
          label: "Disinvestment",
          data: yearData.receipts.disinvestment,
          color: Colors.light.chartColors[3],
          icon: "trending-down" as keyof typeof Ionicons.glyphMap,
        },
        {
          label: "Borrowings",
          data: yearData.receipts.borrowings,
          color: Colors.light.chartColors[4],
          icon: "card" as keyof typeof Ionicons.glyphMap,
        },
      ]
    : [];

  const capitalTotal = capitalItems.reduce((s, c) => s + c.data.be, 0);

  const handleCategoryPress = (category: string, name: string) => {
    router.push({
      pathname: "/receipt/[category]",
      params: { category, name },
    });
  };

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

            <SectionHeader title="BE vs RE vs Actual" subtitle="Last 5 Years Comparison" />
            <View style={styles.chartCard}>
              <GroupedBarChart
                data={groupedBarData}
                height={200}
                barWidth={16}
                groupSpacing={20}
                barGap={2}
                formatValue={formatCroreShort}
                yAxisLabel="in Crores"
              />
            </View>

            <SectionHeader title="Receipt Categories" subtitle={`FY ${selectedYear}`} />
            <View style={styles.chartCard}>
              {receiptCategories.map((cat) => {
                const pct = totalReceipts > 0 ? (cat.value / totalReceipts) * 100 : 0;
                return (
                  <TouchableOpacity
                    key={cat.category}
                    style={styles.categoryRow}
                    onPress={() => handleCategoryPress(cat.category, cat.label)}
                    activeOpacity={0.7}
                  >
                    <View style={[styles.categoryIcon, { backgroundColor: cat.color + "18" }]}>
                      <Ionicons name={cat.icon} size={18} color={cat.color} />
                    </View>
                    <View style={styles.categoryContent}>
                      <View style={styles.categoryHeader}>
                        <Text style={styles.categoryLabel}>{cat.label}</Text>
                        <View style={styles.categoryRight}>
                          <Text style={styles.categoryValue}>{formatCrore(cat.value)}</Text>
                          <Ionicons name="chevron-forward" size={16} color={Colors.light.textSecondary} />
                        </View>
                      </View>
                      <View style={styles.allocationBarBg}>
                        <View
                          style={[
                            styles.allocationBarFill,
                            { width: `${Math.min(pct, 100)}%`, backgroundColor: cat.color },
                          ]}
                        />
                      </View>
                      <Text style={styles.categoryPct}>{pct.toFixed(1)}% of total</Text>
                    </View>
                  </TouchableOpacity>
                );
              })}
            </View>

            {taxBreakdownData.length > 0 && (
              <>
                <SectionHeader title="Tax Revenue Breakdown" subtitle={`FY ${selectedYear}`} />
                <View style={styles.chartCard}>
                  <DonutChart
                    data={taxBreakdownData}
                    size={140}
                    centerLabel="Tax Rev."
                    centerValue={formatCroreShort(yearData.receipts.taxRevenue.be)}
                  />
                </View>
              </>
            )}

            <SectionHeader title="Capital Receipts Detail" subtitle={`FY ${selectedYear}`} />
            <View style={styles.capitalCardsContainer}>
              {capitalItems.map((item) => {
                const pct = capitalTotal > 0 ? (item.data.be / capitalTotal) * 100 : 0;
                return (
                  <TouchableOpacity
                    key={item.label}
                    style={styles.capitalCard}
                    activeOpacity={0.7}
                    onPress={() => handleCategoryPress("capital_receipts", item.label)}
                  >
                    <View style={styles.capitalCardHeader}>
                      <View style={[styles.capitalIcon, { backgroundColor: item.color + "18" }]}>
                        <Ionicons name={item.icon} size={18} color={item.color} />
                      </View>
                      <Text style={styles.capitalCardTitle} numberOfLines={1}>
                        {item.label}
                      </Text>
                    </View>
                    <Text style={styles.capitalCardValue}>{formatCrore(item.data.be)}</Text>
                    <View style={styles.allocationBarBg}>
                      <View
                        style={[
                          styles.allocationBarFill,
                          { width: `${Math.min(pct, 100)}%`, backgroundColor: item.color },
                        ]}
                      />
                    </View>
                    <View style={styles.capitalCardFooter}>
                      <Text style={styles.capitalCardPct}>{pct.toFixed(1)}%</Text>
                      {item.data.re > 0 && (
                        <Text style={styles.capitalCardRe}>RE: {formatCroreShort(item.data.re)}</Text>
                      )}
                    </View>
                  </TouchableOpacity>
                );
              })}
            </View>
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
            formatValue={formatCroreShort}
            yAxisLabel="in Crores"
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
            formatValue={formatCroreShort}
            yAxisLabel="in Crores"
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
  categoryRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: Colors.light.border,
    gap: 12,
  },
  categoryIcon: {
    width: 36,
    height: 36,
    borderRadius: 10,
    justifyContent: "center",
    alignItems: "center",
  },
  categoryContent: {
    flex: 1,
  },
  categoryHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 6,
  },
  categoryLabel: {
    fontSize: 14,
    fontFamily: "Inter_600SemiBold",
    color: Colors.light.text,
  },
  categoryRight: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
  },
  categoryValue: {
    fontSize: 13,
    fontFamily: "Inter_700Bold",
    color: Colors.light.text,
  },
  allocationBarBg: {
    height: 4,
    backgroundColor: Colors.light.border,
    borderRadius: 2,
    overflow: "hidden",
  },
  allocationBarFill: {
    height: 4,
    borderRadius: 2,
  },
  categoryPct: {
    fontSize: 11,
    fontFamily: "Inter_400Regular",
    color: Colors.light.textSecondary,
    marginTop: 3,
  },
  capitalCardsContainer: {
    paddingHorizontal: 16,
    gap: 10,
  },
  capitalCard: {
    backgroundColor: Colors.light.surface,
    borderRadius: 14,
    padding: 14,
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
  capitalCardHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    marginBottom: 8,
  },
  capitalIcon: {
    width: 32,
    height: 32,
    borderRadius: 8,
    justifyContent: "center",
    alignItems: "center",
  },
  capitalCardTitle: {
    fontSize: 14,
    fontFamily: "Inter_600SemiBold",
    color: Colors.light.text,
    flex: 1,
  },
  capitalCardValue: {
    fontSize: 18,
    fontFamily: "Inter_700Bold",
    color: Colors.light.text,
    marginBottom: 8,
  },
  capitalCardFooter: {
    flexDirection: "row",
    justifyContent: "space-between",
    marginTop: 6,
  },
  capitalCardPct: {
    fontSize: 12,
    fontFamily: "Inter_600SemiBold",
    color: Colors.light.textSecondary,
  },
  capitalCardRe: {
    fontSize: 11,
    fontFamily: "Inter_400Regular",
    color: Colors.light.revisedColor,
  },
});
