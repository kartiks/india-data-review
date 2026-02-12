import React, { useState } from "react";
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
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { router } from "expo-router";
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
  expenditure: {
    total: { be: number; re: number; actual: number };
    revenueExpenditure: { be: number; re: number; actual: number };
    capitalExpenditure: { be: number; re: number; actual: number };
    interestPayments: { be: number; re: number; actual: number };
    subsidies: { be: number; re: number; actual: number };
  };
  sectors: Array<{ name: string; id: string; allocation: { be: number; re: number; actual: number } }>;
}

export default function ExpenditureScreen() {
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

  const expBreakdown = yearData
    ? [
        { label: "Revenue Exp.", value: yearData.expenditure.revenueExpenditure.be, color: Colors.light.danger },
        { label: "Capital Exp.", value: yearData.expenditure.capitalExpenditure.be, color: Colors.light.primaryLight },
      ]
    : [];

  const revenueExpDetail = yearData
    ? [
        { label: "Interest Payments", value: yearData.expenditure.interestPayments.be, color: Colors.light.chartColors[4] },
        { label: "Subsidies", value: yearData.expenditure.subsidies.be, color: Colors.light.chartColors[1] },
        {
          label: "Other Revenue Exp.",
          value: yearData.expenditure.revenueExpenditure.be - yearData.expenditure.interestPayments.be - yearData.expenditure.subsidies.be,
          color: Colors.light.chartColors[7],
        },
      ]
    : [];

  const sectorColors = [
    Colors.light.chartColors[0],
    Colors.light.chartColors[1],
    Colors.light.chartColors[2],
    Colors.light.chartColors[3],
    Colors.light.chartColors[4],
    Colors.light.chartColors[5],
    Colors.light.chartColors[6],
    Colors.light.chartColors[7],
    Colors.light.chartColors[8],
    Colors.light.chartColors[9],
  ];

  return (
    <ScrollView
      style={[styles.container, { paddingTop: topPad }]}
      contentContainerStyle={{ paddingBottom: Platform.OS === "web" ? 34 : 100 }}
      showsVerticalScrollIndicator={false}
    >
      <View style={{ paddingTop: insets.top + 8 }}>
        <View style={styles.pageHeader}>
          <Text style={styles.pageTitle}>Expenditure</Text>
          <Text style={styles.pageSubtitle}>Where India spends its money</Text>
        </View>

        <YearSelector years={years} selected={selectedYear} onSelect={setSelectedYear} />

        {yearData && (
          <>
            <View style={styles.cardsRow}>
              <View style={styles.cardHalf}>
                <BudgetCard
                  title="Total Expenditure"
                  value={formatCrore(yearData.expenditure.total.be)}
                  icon="cash"
                  iconColor={Colors.light.danger}
                  subtitle="Budget Estimate"
                />
              </View>
              <View style={styles.cardHalf}>
                <BudgetCard
                  title="Capital Expenditure"
                  value={formatCrore(yearData.expenditure.capitalExpenditure.be)}
                  icon="construct"
                  iconColor={Colors.light.primaryLight}
                  subtitle="Budget Estimate"
                />
              </View>
            </View>

            <SectionHeader title="Revenue vs Capital" subtitle={`FY ${selectedYear}`} />
            <View style={styles.chartCard}>
              <DonutChart
                data={expBreakdown}
                size={140}
                centerLabel="Total"
                centerValue={formatCroreShort(yearData.expenditure.total.be)}
              />
            </View>

            <SectionHeader title="Revenue Exp. Components" subtitle={`FY ${selectedYear}`} />
            <View style={styles.chartCard}>
              <DonutChart
                data={revenueExpDetail}
                size={140}
                centerLabel="Rev. Exp."
                centerValue={formatCroreShort(yearData.expenditure.revenueExpenditure.be)}
              />
            </View>

            <SectionHeader title="Sector-wise Allocation" subtitle={`FY ${selectedYear} (BE)`} />
            <View style={styles.sectorList}>
              {yearData.sectors
                .sort((a, b) => b.allocation.be - a.allocation.be)
                .map((sector, i) => {
                  const totalExp = yearData.expenditure.total.be;
                  const pct = ((sector.allocation.be / totalExp) * 100).toFixed(1);
                  return (
                    <Pressable
                      key={sector.id}
                      style={styles.sectorItem}
                      onPress={() =>
                        router.push({
                          pathname: "/sector/[id]",
                          params: { id: sector.id, name: sector.name },
                        })
                      }
                    >
                      <View style={[styles.sectorDot, { backgroundColor: sectorColors[i % sectorColors.length] }]} />
                      <View style={styles.sectorInfo}>
                        <Text style={styles.sectorName}>{sector.name}</Text>
                        <View style={styles.sectorBarContainer}>
                          <View
                            style={[
                              styles.sectorBar,
                              {
                                width: `${Math.min(parseFloat(pct) * 3, 100)}%`,
                                backgroundColor: sectorColors[i % sectorColors.length],
                              },
                            ]}
                          />
                        </View>
                      </View>
                      <View style={styles.sectorRight}>
                        <Text style={styles.sectorValue}>{formatCrore(sector.allocation.be)}</Text>
                        <Text style={styles.sectorPct}>{pct}%</Text>
                      </View>
                      <Ionicons name="chevron-forward" size={14} color={Colors.light.textSecondary} />
                    </Pressable>
                  );
                })}
            </View>
          </>
        )}

        <SectionHeader title="Expenditure Trend" subtitle="Revenue vs Capital (last 10 years BE)" />
        <View style={styles.chartCard}>
          <LineChart
            labels={last10.map((d) => shortYear(d.year))}
            datasets={[
              {
                data: last10.map((d) => d.expenditure.revenueExpenditure.be),
                color: Colors.light.danger,
                label: "Revenue Exp.",
              },
              {
                data: last10.map((d) => d.expenditure.capitalExpenditure.be),
                color: Colors.light.primaryLight,
                label: "Capital Exp.",
              },
            ]}
            height={220}
            showArea
          />
        </View>

        <SectionHeader title="Interest & Subsidies" subtitle="Trend over last 10 years (BE)" />
        <View style={styles.chartCard}>
          <LineChart
            labels={last10.map((d) => shortYear(d.year))}
            datasets={[
              {
                data: last10.map((d) => d.expenditure.interestPayments.be),
                color: Colors.light.chartColors[4],
                label: "Interest Payments",
              },
              {
                data: last10.map((d) => d.expenditure.subsidies.be),
                color: Colors.light.chartColors[1],
                label: "Subsidies",
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
    paddingHorizontal: 14,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: Colors.light.border,
    gap: 10,
  },
  sectorDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
  },
  sectorInfo: {
    flex: 1,
    gap: 4,
  },
  sectorName: {
    fontSize: 13,
    fontFamily: "Inter_500Medium",
    color: Colors.light.text,
  },
  sectorBarContainer: {
    height: 4,
    backgroundColor: Colors.light.border,
    borderRadius: 2,
  },
  sectorBar: {
    height: 4,
    borderRadius: 2,
  },
  sectorRight: {
    alignItems: "flex-end",
  },
  sectorValue: {
    fontSize: 12,
    fontFamily: "Inter_600SemiBold",
    color: Colors.light.text,
  },
  sectorPct: {
    fontSize: 10,
    fontFamily: "Inter_400Regular",
    color: Colors.light.textSecondary,
  },
});
