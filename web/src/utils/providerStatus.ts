import type { TFunction } from "i18next";
import type { User } from "../api/client";

export function icloudSectionDescription(user: User, t: TFunction): string {
  switch (user.icloud_auth_status) {
    case "authorized":
      return t("userDetail.icloudDescConnected");
    case "not_linked":
      return t("userDetail.icloudDescNotLinked");
    case "not_authorized":
      return t("userDetail.icloudDescNotAuthorized");
    case "reauth_required":
      return t("userDetail.icloudDescReauth");
    case "expired":
      return t("userDetail.icloudDescExpired");
    default:
      return t("userDetail.icloudDesc");
  }
}

export function googleSectionDescription(user: User, t: TFunction): string {
  switch (user.google_auth_status) {
    case "authorized":
      return t("userDetail.googleDescConnected");
    case "not_linked":
      return t("userDetail.googleDescNotLinked");
    case "not_authorized":
      return t("userDetail.googleDescNotAuthorized");
    case "reauth_required":
      return t("userDetail.googleDescReauth");
    default:
      return t("userDetail.googleDesc");
  }
}
