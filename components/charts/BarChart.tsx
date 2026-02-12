import React from "react";
import { View, Text, StyleSheet, ScrollView, Dimensions } from "react-native";
import Svg, { Rect, Text as SvgText, Line, G } from "react-native-svg";
import Colors from "@/constants/colors";

interface BarChartProps {
  data: Array<{ label: string; value: number; color?: string }>;
  height?: number;
  barWidth?: number;
  spacing?: number;
  showValues?: boolean;
  formatValue?: (v: number) => string;
  title?: string;
}

export default function BarChart({
  data,
  height = 200,
  barWidth = 28,
  spacing = 12,
  showValues = true,
  formatValue = (v) => v.toString(),
  title,
}: BarChartProps) {
  const maxVal = Math.max(...data.map((d) => Math.abs(d.value)), 1);
  const chartHeight = height - 40;
  const totalWidth = data.length * (barWidth + spacing) + spacing;
  const screenWidth = Dimensions.get("window").width - 48;
  const svgWidth = Math.max(totalWidth, screenWidth);

  return (
    <View style={styles.container}>
      {title && <Text style={styles.title}>{title}</Text>}
      <ScrollView horizontal showsHorizontalScrollIndicator={false}>
        <Svg width={svgWidth} height={height}>
          <Line
            x1={0}
            y1={chartHeight}
            x2={svgWidth}
            y2={chartHeight}
            stroke={Colors.light.border}
            strokeWidth={1}
          />
          {data.map((item, i) => {
            const barH = (Math.abs(item.value) / maxVal) * (chartHeight - 20);
            const x = spacing + i * (barWidth + spacing);
            const y = chartHeight - barH;
            const color = item.color || Colors.light.chartColors[i % Colors.light.chartColors.length];
            return (
              <G key={i}>
                <Rect
                  x={x}
                  y={y}
                  width={barWidth}
                  height={barH}
                  rx={4}
                  fill={color}
                  opacity={0.9}
                />
                {showValues && (
                  <SvgText
                    x={x + barWidth / 2}
                    y={y - 4}
                    fontSize={8}
                    fill={Colors.light.textSecondary}
                    textAnchor="middle"
                  >
                    {formatValue(item.value)}
                  </SvgText>
                )}
                <SvgText
                  x={x + barWidth / 2}
                  y={chartHeight + 14}
                  fontSize={8}
                  fill={Colors.light.textSecondary}
                  textAnchor="middle"
                  rotation={0}
                >
                  {item.label}
                </SvgText>
              </G>
            );
          })}
        </Svg>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    marginVertical: 8,
  },
  title: {
    fontSize: 14,
    fontFamily: "Inter_600SemiBold",
    color: Colors.light.text,
    marginBottom: 8,
  },
});
