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
import { router } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import Colors from "@/constants/colors";
import SectionHeader from "@/components/SectionHeader";
import LineChart from "@/components/charts/LineChart";
import BarChart from "@/components/charts/BarChart";
import GroupedBarChart from "@/components/charts/GroupedBarChart";
import { formatCrore, formatCroreShort, shortYear } from "@/lib/format";

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
  sectors: Array<{ name: string; id: string; allocation: { be: number } }>;
  devolutionToStates: { be: number; re: number; actual: number };
  centrallySponsoredSchemes: Array<{
    name: string;
    id: string;
    allocation: { be: number; re: number; actual: number };
  }>;
}

interface DeficitData {
  year: string;
  fiscalBE: number;
  fiscalRE: number;
  fiscalActual: number;
  fiscalPctBE: number;
}

export default function TrendsScreen() {
  const insets = useSafeAreaInsets();
  const topPad = Platform.OS === "web" ? 67 : 0;

  const { data: overviewData, isLoading: overviewLoading } = useQuery<OverviewItem[]>({
    queryKey: ["/api/budget/overview"],
  });

  const { data: allData } = useQuery<BudgetYearData[]>({
    queryKey: ["/api/budget/all"],
  });

  const { data: deficitData } = useQuery<DeficitData[]>({
    queryKey: ["/api/budget/deficit"],
  });

  const [selectedSectors, setSelectedSectors] = useState<string[]>(["defence", "health"]);
  const [activeTab, setActiveTab] = useState<"macro" | "sectors" | "fiscal" | "devolution">("macro");

  const sectorOptions = [
    { id: "defence", name: "Defence" },
    { id: "agriculture", name: "Agriculture" },
    { id: "education", name: "Education" },
    { id: "health", name: "Health" },
    { id: "rural_dev", name: "Rural Dev." },
    { id: "transport", name: "Transport" },
    { id: "social_welfare", name: "Social Welfare" },
    { id: "energy", name: "Energy" },
    { id: "science_tech", name: "Science & Tech" },
  ];

  const sectorColors = Colors.light.chartColors;

  if (overviewLoading) {
    return (
      <View style={[styles.loadingContainer, { paddingTop: topPad + insets.top }]}>
        <ActivityIndicator size="large" color={Colors.light.primary} />
      </View>
    );
  }

  const overviewSlice = (overviewData || []).slice(-15);
  const deficitSlice = (deficitData || []).slice(-15);

  const toggleSector = (id: string) => {
    setSelectedSectors((prev) => {
      if (prev.includes(id)) return prev.filter((s) => s !== id);
      if (prev.length >= 4) return prev;
      return [...prev, id];
    });
  };

  const sectorTrendData = selectedSectors.map((sectorId) => {
    const sectorInfo = sectorOptions.find((s) => s.id === sectorId);
    const colorIdx = sectorOptions.findIndex((s) => s.id === sectorId);
    const data = (allData || []).slice(-12).map((year) => {
      const sector = year.sectors.find((s) => s.id === sectorId);
      return sector?.allocation.be || 0;
    });
    return {
      data,
      color: sectorColors[colorIdx % sectorColors.length],
      label: sectorInfo?.name || sectorId,
    };
  });

  const sectorLabels = (allData || []).slice(-12).map((d) => shortYear(d.year));

  const devolutionData = (allData || []).slice(-12);
  const cssData = (allData || []).slice(-12);
  const latestCSS = allData && allData.length > 0 ? allData[allData.length - 1] : null;

  const tabs = [
    { key: "macro" as const, label: "Macro" },
    { key: "sectors" as const, label: "Sectors" },
    { key: "fiscal" as const, label: "Fiscal" },
    { key: "devolution" as const, label: "States & CSS" },
  ];

  return (
    <ScrollView
      style={[styles.container, { paddingTop: topPad }]}
      contentContainerStyle={{ paddingBottom: Platform.OS === "web" ? 34 : 100 }}
      showsVerticalScrollIndicator={false}
    >
      <View style={{ paddingTop: insets.top + 8 }}>
        <View style={styles.pageHeader}>
          <Text style={styles.pageTitle}>Trends</Text>
          <Text style={styles.pageSubtitle}>Multi-year budget analysis</Text>
        </View>

        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.tabBar}
        >
          {tabs.map((tab) => (
            <Pressable
              key={tab.key}
              onPress={() => setActiveTab(tab.key)}
              style={[styles.tab, activeTab === tab.key && styles.tabActive]}
              testID={`tab-${tab.key}`}
              accessibilityRole="button"
              accessibilityLabel={tab.label}
            >
              <Text style={[styles.tabText, activeTab === tab.key && styles.tabTextActive]}>
                {tab.label}
              </Text>
            </Pressable>
          ))}
        </ScrollView>

        {activeTab === "macro" && (
          <>
            <SectionHeader title="GDP Growth Rate" subtitle="Real GDP growth % over years" />
            <View style={styles.chartCard}>
              <BarChart
                data={overviewSlice.map((d) => ({
                  label: shortYear(d.year),
                  value: d.gdpGrowthRate,
                  color: d.gdpGrowthRate >= 0 ? Colors.light.success : Colors.light.danger,
                }))}
                height={200}
                barWidth={22}
                spacing={8}
                formatValue={(v) => `${v.toFixed(1)}%`}
              />
            </View>

            <SectionHeader title="GDP Per Capita" subtitle="Per capita GDP trend (Rs.)" />
            <View style={styles.chartCard}>
              <LineChart
                labels={overviewSlice.map((d) => shortYear(d.year))}
                datasets={[
                  {
                    data: overviewSlice.map((d) => d.gdpPerCapita),
                    color: Colors.light.primaryLight,
                    label: "GDP Per Capita",
                  },
                ]}
                height={200}
                showArea
                formatValue={(v) => `${(v/1000).toFixed(0)}K`}
                yAxisLabel="Rs."
              />
            </View>

            <SectionHeader title="Inflation (CPI)" subtitle="Consumer Price Index % over years" />
            <View style={styles.chartCard}>
              <LineChart
                labels={overviewSlice.map((d) => shortYear(d.year))}
                datasets={[
                  {
                    data: overviewSlice.map((d) => d.inflationCPI),
                    color: Colors.light.danger,
                    label: "CPI Inflation",
                  },
                ]}
                height={200}
                showArea
                formatValue={(v) => `${v.toFixed(1)}%`}
                yAxisLabel="CPI %"
              />
            </View>

            <SectionHeader title="Nominal GDP" subtitle="Total GDP over time" />
            <View style={styles.chartCard}>
              <LineChart
                labels={overviewSlice.map((d) => shortYear(d.year))}
                datasets={[
                  {
                    data: overviewSlice.map((d) => d.gdp),
                    color: Colors.light.primaryLight,
                    label: "GDP",
                  },
                ]}
                height={220}
                showArea
                formatValue={formatCroreShort}
                yAxisLabel="Rs. Cr"
              />
            </View>

            <SectionHeader title="Receipts-to-Expenditure Ratio" subtitle="How much of spending is covered by revenue" />
            <View style={styles.chartCard}>
              <BarChart
                data={overviewSlice.map((d) => ({
                  label: shortYear(d.year),
                  value: d.expenditure > 0 ? (d.receipts / d.expenditure) * 100 : 0,
                  color: d.receipts / d.expenditure > 0.7 ? Colors.light.success : Colors.light.danger,
                }))}
                height={200}
                barWidth={22}
                spacing={8}
                formatValue={(v) => `${v.toFixed(0)}%`}
              />
            </View>
          </>
        )}

        {activeTab === "sectors" && (
          <>
            <SectionHeader title="Sector Comparison" subtitle="Select up to 4 sectors to compare" />
            <ScrollView
              horizontal
              showsHorizontalScrollIndicator={false}
              contentContainerStyle={styles.sectorChips}
            >
              {sectorOptions.map((s, idx) => {
                const isSelected = selectedSectors.includes(s.id);
                return (
                  <Pressable
                    key={s.id}
                    onPress={() => toggleSector(s.id)}
                    style={[
                      styles.sectorChip,
                      isSelected && {
                        backgroundColor: sectorColors[idx % sectorColors.length],
                        borderColor: sectorColors[idx % sectorColors.length],
                      },
                    ]}
                  >
                    <Text style={[styles.sectorChipText, isSelected && styles.sectorChipTextActive]}>
                      {s.name}
                    </Text>
                  </Pressable>
                );
              })}
            </ScrollView>

            {sectorTrendData.length > 0 && (
              <View style={styles.chartCard}>
                <LineChart
                  labels={sectorLabels}
                  datasets={sectorTrendData}
                  height={240}
                  showArea={false}
                  formatValue={formatCroreShort}
                  yAxisLabel="Rs. Cr"
                />
              </View>
            )}

            <SectionHeader title="Sector Growth Comparison" subtitle="YoY Growth % (latest year)" />
            <View style={styles.chartCard}>
              <BarChart
                data={sectorOptions.map((s, idx) => {
                  const allYears = (allData || []);
                  const latest = allYears.length > 0 ? allYears[allYears.length - 1] : null;
                  const prev = allYears.length > 1 ? allYears[allYears.length - 2] : null;
                  const latestSec = latest?.sectors.find((sec) => sec.id === s.id);
                  const prevSec = prev?.sectors.find((sec) => sec.id === s.id);
                  const g = latestSec && prevSec && prevSec.allocation.be > 0
                    ? ((latestSec.allocation.be - prevSec.allocation.be) / prevSec.allocation.be) * 100
                    : 0;
                  return {
                    label: s.name.substring(0, 6),
                    value: g,
                    color: g >= 0 ? sectorColors[idx % sectorColors.length] : Colors.light.danger,
                  };
                })}
                height={200}
                barWidth={20}
                spacing={8}
                formatValue={(v) => `${v.toFixed(1)}%`}
              />
            </View>
          </>
        )}

        {activeTab === "fiscal" && (
          <>
            <SectionHeader title="Fiscal Deficit" subtitle="% of GDP over years (BE)" />
            <View style={styles.chartCard}>
              <LineChart
                labels={deficitSlice.map((d) => shortYear(d.year))}
                datasets={[
                  {
                    data: deficitSlice.map((d) => d.fiscalPctBE),
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

            <SectionHeader title="Deficit Components" subtitle="Fiscal, Revenue & Primary Deficit (BE)" />
            <View style={styles.chartCard}>
              <LineChart
                labels={deficitSlice.map((d) => shortYear(d.year))}
                datasets={[
                  { data: deficitSlice.map((d) => d.fiscalBE), color: Colors.light.danger, label: "Fiscal" },
                  { data: deficitSlice.map((d) => Math.max(d.fiscalRE, 0)), color: Colors.light.accent, label: "Revenue" },
                  { data: deficitSlice.map((d) => Math.max(d.fiscalActual, 0)), color: Colors.light.success, label: "Actual" },
                ]}
                height={220}
                formatValue={formatCroreShort}
                yAxisLabel="Rs. Cr"
              />
            </View>

            <SectionHeader title="Fiscal Deficit BE vs RE vs Actual" subtitle="Comparison over last 5 years" />
            <View style={styles.chartCard}>
              <GroupedBarChart
                data={deficitSlice.slice(-5).map((d) => ({
                  label: shortYear(d.year),
                  values: [
                    { value: d.fiscalBE, color: Colors.light.budgetColor, name: "Budget Est." },
                    { value: Math.max(d.fiscalRE, 0), color: Colors.light.revisedColor, name: "Revised Est." },
                    { value: Math.max(d.fiscalActual, 0), color: Colors.light.actualColor, name: "Actual" },
                  ],
                }))}
                height={220}
                formatValue={formatCroreShort}
                yAxisLabel="Rs. Cr"
              />
            </View>
          </>
        )}

        {activeTab === "devolution" && (
          <>
            <SectionHeader title="Devolution to States" subtitle="Central transfers to state governments (BE)" />
            <View style={styles.chartCard}>
              <LineChart
                labels={devolutionData.map((d) => shortYear(d.year))}
                datasets={[
                  {
                    data: devolutionData.map((d) => d.devolutionToStates?.be || 0),
                    color: Colors.light.primaryLight,
                    label: "Devolution to States",
                  },
                ]}
                height={220}
                showArea
                formatValue={formatCroreShort}
                yAxisLabel="Rs. Cr"
              />
            </View>

            <SectionHeader title="Devolution as % of Total Expenditure" subtitle="Share of budget going to states" />
            <View style={styles.chartCard}>
              <BarChart
                data={devolutionData.map((d, i) => {
                  const totalExp = (overviewData || [])[overviewData!.length - devolutionData.length + i]?.expenditure || 1;
                  const dev = d.devolutionToStates?.be || 0;
                  const pct = (dev / totalExp) * 100;
                  return {
                    label: shortYear(d.year),
                    value: pct,
                    color: Colors.light.primaryLight,
                  };
                })}
                height={200}
                barWidth={22}
                spacing={8}
                formatValue={(v) => `${v.toFixed(1)}%`}
              />
            </View>

            <SectionHeader title="Centrally Sponsored Schemes" subtitle={`FY ${latestCSS?.year || ""} (BE, Rs. Crore)`} />
            {latestCSS && (
              <View style={styles.cssList}>
                {latestCSS.centrallySponsoredSchemes
                  .sort((a, b) => b.allocation.be - a.allocation.be)
                  .map((scheme, i) => {
                    const totalCSS = latestCSS.centrallySponsoredSchemes.reduce((sum, s) => sum + s.allocation.be, 0);
                    const pct = ((scheme.allocation.be / totalCSS) * 100).toFixed(1);
                    return (
                      <View key={scheme.id} style={styles.cssItem}>
                        <View style={[styles.cssDot, { backgroundColor: sectorColors[i % sectorColors.length] }]} />
                        <View style={styles.cssInfo}>
                          <Text style={styles.cssName}>{scheme.name}</Text>
                          <View style={styles.cssBarContainer}>
                            <View
                              style={[
                                styles.cssBar,
                                {
                                  width: `${Math.min(parseFloat(pct) * 2, 100)}%`,
                                  backgroundColor: sectorColors[i % sectorColors.length],
                                },
                              ]}
                            />
                          </View>
                        </View>
                        <View style={styles.cssRight}>
                          <Text style={styles.cssValue}>{formatCrore(scheme.allocation.be)}</Text>
                          <Text style={styles.cssPct}>{pct}%</Text>
                        </View>
                      </View>
                    );
                  })}
              </View>
            )}

            <SectionHeader title="CSS Trends" subtitle="Major centrally sponsored schemes over time" />
            <View style={styles.chartCard}>
              {(() => {
                const cssNames = ["MGNREGA", "PM Awas Yojana", "National Health Mission"];
                const cssColors = [Colors.light.chartColors[0], Colors.light.chartColors[1], Colors.light.chartColors[2]];
                const last8 = (allData || []).slice(-8);
                return (
                  <LineChart
                    labels={last8.map((d) => shortYear(d.year))}
                    datasets={cssNames.map((name, i) => ({
                      data: last8.map((d) => {
                        const s = d.centrallySponsoredSchemes.find(
                          (cs) => cs.name === name || cs.name.startsWith(name.split(" ")[0])
                        );
                        return s?.allocation.be || 0;
                      }),
                      color: cssColors[i],
                      label: name,
                    }))}
                    height={220}
                    formatValue={formatCroreShort}
                    yAxisLabel="Rs. Cr"
                  />
                );
              })()}
            </View>
          </>
        )}
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.light.background },
  loadingContainer: { flex: 1, justifyContent: "center", alignItems: "center", backgroundColor: Colors.light.background },
  pageHeader: { paddingHorizontal: 16, paddingBottom: 12 },
  pageTitle: { fontSize: 24, fontFamily: "Inter_800ExtraBold", color: Colors.light.text },
  pageSubtitle: { fontSize: 13, fontFamily: "Inter_400Regular", color: Colors.light.textSecondary, marginTop: 4 },
  tabBar: { paddingHorizontal: 16, gap: 8, marginBottom: 16 },
  tab: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 20,
    backgroundColor: Colors.light.surface,
    borderWidth: 1,
    borderColor: Colors.light.border,
  },
  tabActive: {
    backgroundColor: Colors.light.primary,
    borderColor: Colors.light.primary,
  },
  tabText: { fontSize: 13, fontFamily: "Inter_500Medium", color: Colors.light.textSecondary },
  tabTextActive: { color: "#fff" },
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
  sectorChips: { paddingHorizontal: 16, gap: 6, marginBottom: 12 },
  sectorChip: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 20,
    backgroundColor: Colors.light.surface,
    borderWidth: 1,
    borderColor: Colors.light.border,
  },
  sectorChipText: { fontSize: 12, fontFamily: "Inter_500Medium", color: Colors.light.textSecondary },
  sectorChipTextActive: { color: "#fff" },
  cssList: {
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
  cssItem: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 14,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: Colors.light.border,
    gap: 10,
  },
  cssDot: { width: 10, height: 10, borderRadius: 5 },
  cssInfo: { flex: 1, gap: 4 },
  cssName: { fontSize: 13, fontFamily: "Inter_500Medium", color: Colors.light.text },
  cssBarContainer: { height: 4, backgroundColor: Colors.light.border, borderRadius: 2 },
  cssBar: { height: 4, borderRadius: 2 },
  cssRight: { alignItems: "flex-end" },
  cssValue: { fontSize: 12, fontFamily: "Inter_600SemiBold", color: Colors.light.text },
  cssPct: { fontSize: 10, fontFamily: "Inter_400Regular", color: Colors.light.textSecondary },
});
