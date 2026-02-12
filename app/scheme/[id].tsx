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
import BarChart from "@/components/charts/BarChart";
import BudgetCard from "@/components/BudgetCard";
import { formatCrore, formatCroreShort, shortYear, getGrowthPercent } from "@/lib/format";

interface SchemeTimeData {
  year: string;
  be: number;
  re: number;
  actual: number;
}

export default function SchemeDetailScreen() {
  const { id, name } = useLocalSearchParams<{ id: string; name: string }>();
  const insets = useSafeAreaInsets();
  const topPad = Platform.OS === "web" ? 67 : 0;

  const { data: schemeData, isLoading } = useQuery<SchemeTimeData[]>({
    queryKey: ["/api/budget/scheme", id],
  });

  const { data: overviewData } = useQuery<Array<{ year: string; expenditure: number }>>({
    queryKey: ["/api/budget/overview"],
  });

  if (isLoading) {
    return (
      <View style={[styles.loadingContainer, { paddingTop: topPad + insets.top }]}>
        <ActivityIndicator size="large" color={Colors.light.primary} />
      </View>
    );
  }

  const validData = (schemeData || []).filter((d) => d.be > 0);
  const last10 = validData.slice(-10);
  const last5 = validData.slice(-5);
  const latest = validData.length > 0 ? validData[validData.length - 1] : null;
  const prevYear = validData.length > 1 ? validData[validData.length - 2] : null;
  const growth = latest && prevYear ? getGrowthPercent(latest.be, prevYear.be) : 0;

  const cagrYears = Math.min(validData.length - 1, 10);
  const cagrStart = validData.length > cagrYears ? validData[validData.length - cagrYears - 1].be : validData[0]?.be || 0;
  const cagrEnd = latest?.be || 0;
  const cagr = cagrStart > 0 && cagrYears > 0
    ? (Math.pow(cagrEnd / cagrStart, 1 / cagrYears) - 1) * 100
    : 0;

  const overviewSlice = (overviewData || []).slice(-last10.length);
  const totalBudgetGrowth = last10.slice(1).map((d, i) => {
    const overIdx = overviewSlice.length - last10.length + i;
    const prevBudget = overIdx >= 0 && overIdx < overviewSlice.length ? overviewSlice[overIdx]?.expenditure || 0 : 0;
    const currBudget = overIdx + 1 >= 0 && overIdx + 1 < overviewSlice.length ? overviewSlice[overIdx + 1]?.expenditure || 0 : 0;
    return {
      label: shortYear(d.year),
      value: prevBudget > 0 ? ((currBudget - prevBudget) / prevBudget) * 100 : 0,
    };
  });

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
          <Text style={styles.pageTitle} numberOfLines={2}>{name || id}</Text>
          <Text style={styles.pageSubtitle}>Scheme allocation trends</Text>
        </View>
      </View>

      <View style={styles.cardsRow}>
        <View style={styles.cardHalf}>
          <BudgetCard
            title="Latest BE"
            value={formatCrore(latest?.be || 0)}
            icon="analytics"
            iconColor={Colors.light.primary}
            growth={growth}
            subtitle={`FY ${latest?.year || ""}`}
          />
        </View>
        <View style={styles.cardHalf}>
          <BudgetCard
            title={`${cagrYears}Y CAGR`}
            value={`${cagr.toFixed(1)}%`}
            icon="trending-up"
            iconColor={Colors.light.success}
            subtitle="Compound Annual Growth"
          />
        </View>
      </View>

      <SectionHeader title="BE vs RE vs Actual" subtitle="Last 5 years comparison" />
      <View style={styles.chartCard}>
        <GroupedBarChart
          data={last5.map((d) => ({
            label: shortYear(d.year),
            values: [
              { value: d.be, color: Colors.light.budgetColor, name: "Budget Est." },
              { value: d.re, color: Colors.light.revisedColor, name: "Revised Est." },
              { value: d.actual, color: Colors.light.actualColor, name: "Actual" },
            ],
          }))}
          height={220}
          formatValue={formatCroreShort}
          yAxisLabel="in Crores"
        />
      </View>

      <SectionHeader title="Allocation Trend" subtitle="Budget Estimates over time" />
      <View style={styles.chartCard}>
        <LineChart
          labels={last10.map((d) => shortYear(d.year))}
          datasets={[
            {
              data: last10.map((d) => d.be),
              color: Colors.light.primary,
              label: "Budget Estimate",
            },
          ]}
          height={200}
          showArea
          formatValue={formatCroreShort}
          yAxisLabel="in Crores"
        />
      </View>

      <SectionHeader title="Year-on-Year Growth" subtitle="% change in BE with total budget trendline" />
      <View style={styles.chartCard}>
        <BarChart
          data={last10.slice(1).map((d, i) => {
            const prev = last10[i].be;
            const growthPct = prev > 0 ? ((d.be - prev) / prev) * 100 : 0;
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
          trendlineData={totalBudgetGrowth}
          trendlineColor={Colors.light.textSecondary}
          trendlineLabel="Total Budget YoY Growth"
        />
      </View>

      <SectionHeader title="Historical Data" subtitle="All years (Rs. Crore)" />
      <View style={styles.tableCard}>
        <View style={styles.tableHeader}>
          <Text style={[styles.tableCell, styles.tableHeaderText, { flex: 1.2 }]}>Year</Text>
          <Text style={[styles.tableCell, styles.tableHeaderText, { flex: 1 }]}>BE</Text>
          <Text style={[styles.tableCell, styles.tableHeaderText, { flex: 1 }]}>RE</Text>
          <Text style={[styles.tableCell, styles.tableHeaderText, { flex: 1 }]}>Actual</Text>
        </View>
        {validData.slice().reverse().map((row) => (
          <View key={row.year} style={styles.tableRow}>
            <Text style={[styles.tableCell, { flex: 1.2, fontFamily: "Inter_500Medium" }]}>{row.year}</Text>
            <Text style={[styles.tableCell, { flex: 1 }]}>{formatCroreShort(row.be)}</Text>
            <Text style={[styles.tableCell, { flex: 1 }]}>{row.re > 0 ? formatCroreShort(row.re) : "-"}</Text>
            <Text style={[styles.tableCell, { flex: 1 }]}>{row.actual > 0 ? formatCroreShort(row.actual) : "-"}</Text>
          </View>
        ))}
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
  pageTitle: { fontSize: 20, fontFamily: "Inter_800ExtraBold", color: Colors.light.text },
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
